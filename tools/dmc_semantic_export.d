// Optional signature handoff inserted into an output copy of out.d.
// The process owns all DMC pointers; the stream contains only copied values.
version (SCPP)
{
extern (D):
@trusted
private void tinypp_semantic_failure()
{
    import core.stdc.stdlib : exit;
    fputs("tinypp: semantic signature export failed\n", stderr);
    exit(1);
}

@trusted
private void tinypp_semantic_hex(FILE* stream, const(char)* text)
{
    if (!text)
        tinypp_semantic_failure();
    fputc('"', stream);
    uint index = 0;
    while (text[index])
    {
        if (index == 512)
            tinypp_semantic_failure();
        fprintf(stream, "%02x", cast(uint)cast(ubyte)text[index]);
        ++index;
    }
    fputc('"', stream);
}

@trusted
private void tinypp_semantic_path(FILE* stream, Symbol* symbol, uint depth)
{
    if (!symbol || depth == 32)
        tinypp_semantic_failure();
    if (symbol.Sscope)
    {
        tinypp_semantic_path(stream, symbol.Sscope, depth + 1);
        fputc(',', stream);
    }
    tinypp_semantic_hex(stream, symbol.Sident.ptr);
}

@trusted
private void tinypp_semantic_type(FILE* stream, type* value, uint depth)
{
    if (!value || depth == 32)
        tinypp_semantic_failure();
    const(char)* kind;
    tym_t basic = tybasic(value.Tty);
    switch (basic)
    {
        case TYvoid: kind = "void"; break;
        case TYbool: kind = "bool"; break;
        case TYchar: kind = "char"; break;
        case TYschar: kind = "signed-char"; break;
        case TYuchar: kind = "unsigned-char"; break;
        case TYshort: kind = "short"; break;
        case TYushort: kind = "unsigned-short"; break;
        case TYint: kind = "int"; break;
        case TYuint: kind = "unsigned-int"; break;
        case TYlong: kind = "long"; break;
        case TYulong: kind = "unsigned-long"; break;
        case TYfloat: kind = "float"; break;
        case TYdouble: kind = "double"; break;
        case TYdouble_alias: kind = "long-double"; break;
        case TYldouble: kind = "long-double"; break;
        case TYwchar_t: kind = "wchar-t"; break;
        case TYnptr: kind = "pointer"; break;
        case TYref: kind = "lvalue-reference"; break;
        case TYstruct: kind = "record"; break;
        default: kind = "unsupported"; break;
    }
    fprintf(stream, "{\"kind\":\"%s\",\"const\":%s,\"volatile\":%s",
        kind, (value.Tty & mTYconst ? "true" : "false").ptr,
        (value.Tty & mTYvolatile ? "true" : "false").ptr);
    if (basic == TYnptr || basic == TYref)
    {
        fputs(",\"to\":", stream);
        tinypp_semantic_type(stream, value.Tnext, depth + 1);
    }
    else if (basic == TYstruct)
    {
        if (value.Ttag.Sstruct.Sstructsize > uint.max)
            tinypp_semantic_failure();
        fputs(",\"path_hex\":[", stream);
        tinypp_semantic_path(stream, value.Ttag, 0);
        fprintf(stream, "],\"bytes\":%u,\"alignment\":%u",
            cast(uint)value.Ttag.Sstruct.Sstructsize,
            value.Ttag.Sstruct.Salignsize);
    }
    else if (strcmp(kind, "unsupported") == 0)
        fprintf(stream, ",\"raw_type\":%u", basic);
    else
        fprintf(stream, ",\"bytes\":%u",
            basic == TYvoid ? 0 : cast(uint)tysize(basic));
    fputc('}', stream);
}

@trusted
private void tinypp_semantic_signature(Symbol* subject)
{
    import core.stdc.stdlib : getenv;
    __gshared uint records;
    const(char)* filename = getenv("TINYPP_SEMANTIC_EXPORT");
    if (!filename || !*filename)
        return;
    if (records == 4096 ||
        (config.exe != EX_WIN32 && config.exe != EX_WIN64))
        tinypp_semantic_failure();
    FILE* stream = fopen(filename, records ? "ab" : "wb");
    if (!stream)
        tinypp_semantic_failure();
    if (fseek(stream, 0, SEEK_END) != 0)
        tinypp_semantic_failure();
    long start = ftell(stream);
    if (start < 0)
        tinypp_semantic_failure();
    ++records;
    type* signature = subject.Stype;
    const(char)* category = subject.Sfunc.Fflags & Fctor ? "constructor"
        : subject.Sfunc.Fflags & Fdtor ? "destructor" : "function";
    const(char)* language = type_mangle(signature) == mTYman_cpp ? "c++"
        : type_mangle(signature) == mTYman_c ? "c" : "unsupported";
    fprintf(stream, "{\"schema\":\"tinypp.semantic-signature.v1\","
        ~ "\"target\":\"%s\",\"abi\":\"dmc-experimental-v1\","
        ~ "\"function_kind\":\"%s\",\"linkage\":\"%s\",\"path_hex\":[",
        (config.exe == EX_WIN64 ? "windows-x64" : "windows-x86").ptr,
        category, language);
    tinypp_semantic_path(stream, subject, 0);
    fprintf(stream, "],\"const_member\":%s,\"volatile_member\":%s,"
        ~ "\"variadic\":%s,\"result\":",
        (signature.Tty & mTYconst ? "true" : "false").ptr,
        (signature.Tty & mTYvolatile ? "true" : "false").ptr,
        (signature.Tflags & TFfixed ? "false" : "true").ptr);
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
    fputs("]}\n", stream);
    long finish = ftell(stream);
    bool failed = ferror(stream) != 0 || finish < start ||
        finish > 4 * 1024 * 1024 || finish - start > 65536;
    if (fclose(stream) != 0 || failed)
        tinypp_semantic_failure();
}
}
