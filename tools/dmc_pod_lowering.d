// Tiny++ experimental adaptation inserted into an output copy of out.d.
// Imports and extern(C++) scope come from that file. Not a standalone module.
// Preserve semantic parameter types until after inline expansion.
version (SCPP)
{
private enum bool tinypp_indirect_nontrivial = false;

@trusted
private bool tinypp_indirect_pod_type(type* t)
{
    if (tybasic(t.Tty) != TYstruct)
        return false;
    // STRnotpod is populated by shared D type construction, not reliably
    // by the SCPP parser. Inspect its copy/destructor records as well.
    auto aggregate = t.Ttag.Sstruct;
    bool nontrivial = aggregate.Sdtor !is null ||
        (aggregate.Scpct !is null &&
         !(aggregate.Scpct.Sfunc.Fflags & Fbitcopy));
    if (aggregate.Sflags & STRnotpod || nontrivial)
        return tinypp_indirect_nontrivial;
    targ_size_t size = type_size(t);
    return size != 1 && size != 2 && size != 4 && size != 8;
}

@trusted
private elem* tinypp_indirect_pod_uses(elem* e, Symbol* original,
                                     Symbol* parameter)
{
    if (!e)
        return null;
    if ((e.Eoper == OPvar || e.Eoper == OPrelconst) &&
        e.EV.Vsym == original)
    {
        elem* address = el_var(parameter);
        if (e.EV.Voffset)
            address = el_bint(OPadd, parameter.Stype, address,
                             el_longt(tssize, e.EV.Voffset));
        elem* replacement = e.Eoper == OPvar
            ? el_unat(OPind, e.ET, address) : el_settype(address, e.ET);
        replacement.Esrcpos = e.Esrcpos;
        replacement.PEFflags = e.PEFflags;
        replacement.Emember = e.Emember;
        el_free(e);
        return replacement;
    }
    if (OTbinary(e.Eoper))
        e.EV.E2 = tinypp_indirect_pod_uses(e.EV.E2, original, parameter);
    if (!OTleaf(e.Eoper))
        e.EV.E1 = tinypp_indirect_pod_uses(e.EV.E1, original, parameter);
    return e;
}

@trusted
private elem* tinypp_indirect_pod_arguments(elem* e)
{
    if (!e)
        return null;
    if (OTbinary(e.Eoper))
        e.EV.E2 = tinypp_indirect_pod_arguments(e.EV.E2);
    if (!OTleaf(e.Eoper))
        e.EV.E1 = tinypp_indirect_pod_arguments(e.EV.E1);
    if ((e.Eoper != OPstrpar &&
         !(tinypp_indirect_nontrivial && e.Eoper == OPstrctor)) ||
        !tinypp_indirect_pod_type(e.ET))
        return e;
    type* t = e.ET;
    Symbol* temporary = symbol_generate(SCauto, t);
    temporary.Sflags |= SFLfree;
    temporary.Salignment = 16;
    symbol_add(globsym, temporary);
    elem* value = e.EV.E1;
    e.EV.E1 = null;
    elem* address = el_ptr(temporary);
    elem* copy;
    if (e.Eoper == OPstrctor)
    {
        // Keep the semantic copy constructor and its lifetime markers.
        // Construct directly in the ABI temporary; never byte-copy it.
        exp2_setstrthis(value, temporary, 0, address.ET);
        copy = value;
    }
    else
        copy = el_bint(OPstreq, t, el_var(temporary), value);
    elem* replacement = el_bint(OPcomma, address.ET, copy, address);
    replacement.Esrcpos = e.Esrcpos;
    el_free(e);
    return replacement;
}

@trusted
private void tinypp_lower_pod_parameters()
{
    if (!I64 || config.exe != EX_WIN64 || !CPP)
        return;
    for (int si = 0; si < globsym.length; ++si)
    {
        Symbol* original = globsym[si];
        type* t = original.Stype;
        if (original.Sclass != SCparameter || !tinypp_indirect_pod_type(t))
            continue;
        Symbol* parameter = symbol_copy(original);
        type_free(parameter.Stype);
        parameter.Stype = newpointer(t);
        parameter.Stype.Tcount++;
        globsym[si] = parameter;
        for (block* b = startblock; b; b = b.Bnext)
            b.Belem = tinypp_indirect_pod_uses(b.Belem, original, parameter);
    }
    for (block* b = startblock; b; b = b.Bnext)
        b.Belem = tinypp_indirect_pod_arguments(b.Belem);
}
}
