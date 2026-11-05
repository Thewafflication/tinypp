// Optional typed body stream. Inserted into an output copy, not upstream.
// Called after semantic blocks are available and before inline/ABI lowering.
version (SCPP)
{
extern (D):
private __gshared block*[512] tinypp_ir_blocks;
private __gshared uint tinypp_ir_block_count;
private __gshared uint tinypp_ir_nodes;

@trusted
private int tinypp_ir_symbol(Symbol* symbol)
{
    for (int index = 0; index < globsym.length; ++index)
        if (globsym[index] == symbol)
            return index;
    return -1;
}

@trusted
private uint tinypp_ir_block_id(block* candidate)
{
    for (uint index = 0; index < tinypp_ir_block_count; ++index)
        if (tinypp_ir_blocks[index] == candidate)
            return index;
    tinypp_semantic_failure();
    return 0;
}

@trusted
private Symbol* tinypp_ir_dependency(Symbol* subject)
{
    if (!subject)
        tinypp_semantic_failure();
    uint aliases = 0;
    while (subject.Sclass == SCfuncalias)
    {
        if (++aliases == 32)
            tinypp_semantic_failure();
        subject = subject.Sfunc.Falias;
    }
    // Native outelem normally discovers these dependencies. The semantic-only
    // path must queue their bodies without entering native code generation.
    nwc_mustwrite(subject);
    return subject;
}

@trusted
private void tinypp_ir_dependencies(elem* value, uint depth, ref uint nodes)
{
    if (!value)
        return;
    if (depth == 64 || ++nodes > 4096)
        tinypp_semantic_failure();
    // OPctor stores its destructor outside the ordinary expression children.
    // Unsupported nodes still own dependencies, even though the importer must
    // reject their operations. Never mistake incomplete traversal for closure.
    if (value.Eoper == OPctor)
        tinypp_ir_dependency(value.EV.Edtor);
    if ((value.Eoper == OPvar || value.Eoper == OPrelconst) &&
        value.ET && tyfunc(value.ET.Tty))
        tinypp_ir_dependency(value.EV.Vsym);
    if (OTunary(value.Eoper) || OTbinary(value.Eoper))
        tinypp_ir_dependencies(value.EV.E1, depth + 1, nodes);
    if (OTbinary(value.Eoper))
        tinypp_ir_dependencies(value.EV.E2, depth + 1, nodes);
}

@trusted
private void tinypp_ir_function(FILE* stream, Symbol* subject)
{
    subject = tinypp_ir_dependency(subject);
    type* signature = subject.Stype;
    fputs("{\"path_hex\":[", stream);
    tinypp_semantic_path(stream, subject, 0);
    fprintf(stream, "],\"linkage\":\"%s\",\"function_kind\":\"%s\","
        ~ "\"const_member\":%s,\"volatile_member\":%s,\"variadic\":%s,"
        ~ "\"internal\":%s,\"result\":",
        (type_mangle(signature) == mTYman_cpp ? "c++" :
            type_mangle(signature) == mTYman_c ? "c" : "unsupported").ptr,
        (strncmp(subject.Sident.ptr, "__SI", 4) == 0 ? "unsupported" :
            subject.Sfunc.Fflags & Fctor ? "constructor" :
            subject.Sfunc.Fflags & Fdtor ? "destructor" : "function").ptr,
        (signature.Tty & mTYconst ? "true" : "false").ptr,
        (signature.Tty & mTYvolatile ? "true" : "false").ptr,
        (signature.Tflags & TFfixed ? "false" : "true").ptr,
        (subject.Sclass == SCstatic ? "true" : "false").ptr);
    if (subject.Sfunc.Fflags & (Fctor | Fdtor))
        fputs("null", stream);
    else
        tinypp_semantic_type(stream, signature.Tnext, 0);
    fputs(",\"parameters\":[", stream);
    uint count = 0;
    for (param_t* parameter = signature.Tparamtypes; parameter;
         parameter = parameter.Pnext)
    {
        if (count == 256)
            tinypp_semantic_failure();
        if (count++)
            fputc(',', stream);
        tinypp_semantic_type(stream, parameter.Ptype, 0);
    }
    fputs("],\"receiver\":", stream);
    if (subject.Sfunc.Fclass && !(subject.Sfunc.Fflags & Fstatic))
    {
        type* receiver = cpp_thistype(signature, subject.Sfunc.Fclass);
        tinypp_semantic_type(stream, receiver, 0);
        type_free(receiver);
    }
    else
        fputs("null", stream);
    fputs(",\"lowered_result\":", stream);
    tinypp_semantic_type(stream, signature.Tnext, 0);
    fputc('}', stream);
}

@trusted
private const(char)* tinypp_ir_operation(uint operation)
{
    switch (operation)
    {
        case OPadd: return "add";
        case OPmin: return "subtract";
        case OPmul: return "multiply";
        case OPdiv: return "divide";
        case OPmod: return "remainder";
        case OPshl: return "shift-left";
        case OPshr: case OPashr: return "shift-right";
        case OPand: return "bit-and";
        case OPor: return "bit-or";
        case OPxor: return "bit-xor";
        case OPandand: return "logical-and";
        case OPoror: return "logical-or";
        case OPle: return "less-equal";
        case OPgt: return "greater";
        case OPlt: return "less";
        case OPge: return "greater-equal";
        case OPeqeq: return "equal";
        case OPne: return "not-equal";
        case OPeq: return "assign";
        case OPaddass: return "add-assign";
        case OPminass: return "subtract-assign";
        case OPmulass: return "multiply-assign";
        case OPdivass: return "divide-assign";
        case OPmodass: return "remainder-assign";
        case OPpostinc: return "post-add";
        case OPpostdec: return "post-subtract";
        case OPcomma: return "comma";
        case OPnot: return "logical-not";
        case OPbool: return "booleanize";
        case OPcom: return "bit-not";
        case OPneg: return "negate";
        case OPuadd: return "positive";
        case OPvoid: return "discard";
        case OPind: return "indirect";
        case OPaddr: return "address";
        default: return "unsupported";
    }
}

@trusted
private void tinypp_ir_expression(FILE* stream, elem* value, uint depth);

@trusted
private void tinypp_ir_arguments(FILE* stream, elem* value, bool reverse,
                                 ref uint count, uint depth)
{
    if (!value || depth == 64)
        tinypp_semantic_failure();
    if (value.Eoper == OPparam)
    {
        tinypp_ir_arguments(stream, reverse ? value.EV.E1 : value.EV.E2,
                            reverse, count, depth + 1);
        tinypp_ir_arguments(stream, reverse ? value.EV.E2 : value.EV.E1,
                            reverse, count, depth + 1);
        return;
    }
    if (count == 256)
        tinypp_semantic_failure();
    if (count++)
        fputc(',', stream);
    tinypp_ir_expression(stream, value, depth + 1);
}

@trusted
private Symbol* tinypp_ir_callee(elem* value)
{
    // A direct destructor call is *( &function ), not a function-pointer load.
    // Peel only that exact identity-preserving wrapper; dynamic calls remain
    // unsupported until their own dispatch contract is implemented.
    if (value.Eoper == OPind && value.EV.E1.Eoper == OPaddr)
        value = value.EV.E1.EV.E1;
    if (value.Eoper == OPvar && tyfunc(value.ET.Tty) &&
        value.EV.Voffset == 0)
        return value.EV.Vsym;
    return null;
}

@trusted
private void tinypp_ir_expression(FILE* stream, elem* value, uint depth)
{
    if (!value)
    {
        fputs("null", stream);
        return;
    }
    if (depth == 64 || ++tinypp_ir_nodes > 4096 || !value.ET)
        tinypp_semantic_failure();
    uint operation = value.Eoper;
    const(char)* name = tinypp_ir_operation(operation);
    if (operation == OPconst)
        name = "literal";
    else if (operation == OPvar && !tyfunc(value.ET.Tty))
        name = "variable";
    else if (operation == OPrelconst)
        name = "variable-address";
    else if ((operation == OPcall || operation == OPucall ||
              operation == OPcallns || operation == OPucallns) &&
             tinypp_ir_callee(value.EV.E1))
        name = "call";
    else if (operation == OPadd && typtr(value.ET.Tty) &&
             typtr(value.EV.E1.ET.Tty) &&
             tybasic(value.EV.E1.ET.Tnext.Tty) == TYstruct &&
             value.EV.E2.Eoper == OPconst &&
             tyintegral(value.EV.E2.ET.Tty))
        name = "field-address";
    else if (operation == OPcond && value.EV.E2.Eoper == OPcolon)
        name = "conditional";
    fprintf(stream, "{\"op\":\"%s\",\"type\":", name);
    tinypp_semantic_type(stream, value.ET, 0);
    if (strcmp(name, "literal") == 0)
    {
        tym_t basic = tybasic(value.ET.Tty);
        if (basic == TYuint || basic == TYulong)
            fprintf(stream, ",\"value\":\"%u\"", cast(uint)value.EV.Vullong);
        else
            fprintf(stream, ",\"value\":\"%d\"", cast(int)value.EV.Vllong);
    }
    else if (strcmp(name, "variable") == 0 ||
             strcmp(name, "variable-address") == 0)
        fprintf(stream, ",\"id\":%d,\"offset\":%d",
            tinypp_ir_symbol(value.EV.Vsym), cast(int)value.EV.Voffset);
    else if (strcmp(name, "call") == 0)
    {
        Symbol* callee = tinypp_ir_dependency(tinypp_ir_callee(value.EV.E1));
        bool member = callee.Sfunc.Fclass &&
            !(callee.Sfunc.Fflags & Fstatic);
        elem* arguments = null;
        elem* receiver = null;
        if (operation == OPcall || operation == OPcallns)
            arguments = value.EV.E2;
        if (member)
        {
            // xfunccall appends the receiver outside the explicit arguments.
            // Do not flatten it according to the function's argument order.
            if (!arguments)
                tinypp_semantic_failure();
            if (arguments.Eoper == OPparam)
            {
                receiver = arguments.EV.E2;
                arguments = arguments.EV.E1;
            }
            else
            {
                receiver = arguments;
                arguments = null;
            }
        }
        fputs(",\"function\":", stream);
        tinypp_ir_function(stream, callee);
        fputs(",\"receiver\":", stream);
        tinypp_ir_expression(stream, receiver, depth + 1);
        fputs(",\"args\":[", stream);
        uint count = 0;
        if (arguments)
            tinypp_ir_arguments(stream, arguments,
                tyrevfunc(callee.Stype.Tty) != 0, count, depth + 1);
        fputc(']', stream);
    }
    else if (strcmp(name, "field-address") == 0)
    {
        fprintf(stream, ",\"offset\":%lld,\"args\":[",
                cast(long)value.EV.E2.EV.Vllong);
        tinypp_ir_expression(stream, value.EV.E1, depth + 1);
        fputc(']', stream);
    }
    else if (strcmp(name, "unsupported") == 0)
        fprintf(stream, ",\"raw_operation\":%u", operation);
    else
    {
        fputs(",\"args\":[", stream);
        tinypp_ir_expression(stream, value.EV.E1, depth + 1);
        if (strcmp(name, "conditional") == 0)
        {
            fputc(',', stream);
            tinypp_ir_expression(stream, value.EV.E2.EV.E1, depth + 1);
            fputc(',', stream);
            tinypp_ir_expression(stream, value.EV.E2.EV.E2, depth + 1);
        }
        else if (OTbinary(operation))
        {
            fputc(',', stream);
            tinypp_ir_expression(stream, value.EV.E2, depth + 1);
        }
        fputc(']', stream);
    }
    fputc('}', stream);
}

@trusted
private bool tinypp_semantic_body(Symbol* subject)
{
    import core.stdc.stdlib : getenv;
    __gshared uint functions;
    const(char)* filename = getenv("TINYPP_SEMANTIC_BODY");
    const(char)* mode = getenv("TINYPP_SEMANTIC_BODY_ONLY");
    bool only = mode && strcmp(mode, "1") == 0;
    if (mode && *mode && !only)
        tinypp_semantic_failure();
    if (!filename || !*filename)
    {
        if (only)
            tinypp_semantic_failure();
        return false;
    }
    if (++functions > 256 || globsym.length > 1024 ||
        (config.exe != EX_WIN32 && config.exe != EX_WIN64))
        tinypp_semantic_failure();
    tinypp_ir_block_count = 0;
    tinypp_ir_nodes = 0;
    uint dependencyNodes = 0;
    for (block* item = startblock; item; item = item.Bnext)
    {
        if (tinypp_ir_block_count == 512)
            tinypp_semantic_failure();
        tinypp_ir_blocks[tinypp_ir_block_count++] = item;
        tinypp_ir_dependencies(item.Belem, 0, dependencyNodes);
    }
    FILE* stream = fopen(filename, functions == 1 ? "wb" : "ab");
    if (!stream || fseek(stream, 0, SEEK_END) != 0)
        tinypp_semantic_failure();
    long start = ftell(stream);
    fprintf(stream, "{\"schema\":\"tinypp.function-ir.v2\",\"target\":\"%s\","
        ~ "\"abi\":\"dmc-experimental-v1\",\"emission\":\"%s\",\"function\":",
        (config.exe == EX_WIN64 ? "windows-x64" : "windows-x86").ptr,
        (only ? "semantic-only" : "legacy-observation").ptr);
    tinypp_ir_function(stream, subject);
    fputs(",\"variables\":[", stream);
    // DMC inserts explicit parameters backwards for tyrevfunc conventions.
    // Preserve expression IDs, but publish bindings in logical source order.
    uint[1024] order;
    uint count = 0;
    for (uint index = 0; index < globsym.length; ++index)
        if (globsym[index].Sclass == SCparameter)
            order[count++] = index;
    if (tyrevfunc(subject.Stype.Tty))
    {
        uint first = subject.Sfunc.Fclass &&
            !(subject.Sfunc.Fflags & Fstatic) ? 1 : 0;
        uint last = count;
        while (first < last)
        {
            --last;
            uint temporary = order[first];
            order[first++] = order[last];
            order[last] = temporary;
        }
    }
    for (uint index = 0; index < globsym.length; ++index)
        if (globsym[index].Sclass != SCparameter)
            order[count++] = index;
    for (uint slot = 0; slot < count; ++slot)
    {
        uint index = order[slot];
        Symbol* symbol = globsym[index];
        if (slot)
            fputc(',', stream);
        fprintf(stream, "{\"id\":%d,\"storage\":\"%s\",\"type\":", index,
            (symbol.Sclass == SCparameter ? "parameter" :
             symbol.Sclass == SCauto || symbol.Sclass == SCregister
                ? "local" : "unsupported").ptr);
        tinypp_semantic_type(stream, symbol.Stype, 0);
        fputc('}', stream);
    }
    fputs("],\"blocks\":[", stream);
    for (uint index = 0; index < tinypp_ir_block_count; ++index)
    {
        block* item = tinypp_ir_blocks[index];
        if (index)
            fputc(',', stream);
        const(char)* exitKind = item.BC == BCgoto ? "goto" :
            item.BC == BCiftrue ? "branch" : item.BC == BCret ? "return" :
            item.BC == BCretexp ? "return-value" : "unsupported";
        fprintf(stream, "{\"id\":%u,\"exit\":\"%s\",\"successors\":[",
            index, exitKind);
        for (int next = 0; next < item.numSucc(); ++next)
        {
            if (next)
                fputc(',', stream);
            fprintf(stream, "%u", tinypp_ir_block_id(item.nthSucc(next)));
        }
        fputs("],\"expression\":", stream);
        tinypp_ir_expression(stream, item.Belem, 0);
        fputc('}', stream);
    }
    fputs("]}\n", stream);
    long finish = ftell(stream);
    bool failed = ferror(stream) != 0 || start < 0 || finish < start ||
        finish > 8 * 1024 * 1024 || finish - start > 1024 * 1024;
    if (fclose(stream) != 0 || failed)
        tinypp_semantic_failure();
    return only;
}
}
