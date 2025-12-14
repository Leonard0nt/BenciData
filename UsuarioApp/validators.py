from django.core.exceptions import ValidationError


def _clean_rut(value: str) -> str:
    # Remove dots, spaces and to upper
    return value.replace(".", "").replace(" ", "").replace("-", "").upper()


def validate_rut(value: str):
    """Validate Chilean RUT with check digit.

    Accepts formats like '12.345.678-5', '12345678-5' or '123456785'.
    Raises ValidationError if invalid.
    """
    if not value:
        raise ValidationError("RUT inválido.")

    clean = _clean_rut(value)
    if len(clean) < 2:
        raise ValidationError("RUT inválido.")

    number, dv = clean[:-1], clean[-1]
    if not number.isdigit():
        raise ValidationError("RUT inválido.")

    # Calculate verifier
    reversed_digits = map(int, reversed(number))
    factors = [2, 3, 4, 5, 6, 7]
    total = 0
    factor_index = 0
    for d in reversed_digits:
        total += d * factors[factor_index]
        factor_index = (factor_index + 1) % len(factors)

    remainder = total % 11
    check = 11 - remainder
    if check == 11:
        expected = "0"
    elif check == 10:
        expected = "K"
    else:
        expected = str(check)

    if dv != expected:
        raise ValidationError("RUT inválido (dígito verificador no coincide).")
