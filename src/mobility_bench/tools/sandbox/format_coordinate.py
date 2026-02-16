def format_decimal_places(value):
    if isinstance(value, str) and ',' in value:
        parts = value.split(',')
        return ",".join([format_decimal_places(p.strip()) for p in parts])
    s = str(value)
    
    if '.' not in s:
        # 整数情况
        return s + '.000000'
    else:
        integer_part, decimal_part = s.split('.', 1)
        if len(decimal_part) < 6:
            decimal_part = decimal_part.ljust(6, '0')  # 右侧补0
        return integer_part + '.' + decimal_part