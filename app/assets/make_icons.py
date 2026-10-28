import cairosvg
FILL = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 72 72">
<rect x="2" y="2" width="68" height="68" rx="14" fill="#2F3B70"/>
<path d="M36 14 V56 M24 58 H48" stroke="#FFFFFF" stroke-width="4" stroke-linecap="round"/>
<path d="M14 22 H58" stroke="#FFFFFF" stroke-width="4" stroke-linecap="round"/>
<path d="M14 22 L7 38 H21 Z M58 22 L51 38 H65 Z" fill="none" stroke="#FFFFFF" stroke-width="2.5" stroke-linejoin="round"/>
<path d="M6 38 a8 6 0 0 0 16 0 Z" fill="#E5534B"/><path d="M50 38 a8 6 0 0 0 16 0 Z" fill="#3FB68B"/>
<circle cx="36" cy="14" r="4" fill="#FFFFFF"/></svg>'''
# for the dark Splunk bar: no background square, white scale
ALT = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 72 72">
<path d="M36 12 V58 M22 61 H50" stroke="#FFFFFF" stroke-width="5" stroke-linecap="round"/>
<path d="M10 21 H62" stroke="#FFFFFF" stroke-width="5" stroke-linecap="round"/>
<path d="M10 21 L2 40 H18 Z M62 21 L54 40 H70 Z" fill="none" stroke="#FFFFFF" stroke-width="3" stroke-linejoin="round"/>
<path d="M1 40 a9 7 0 0 0 18 0 Z" fill="#F07068"/><path d="M53 40 a9 7 0 0 0 18 0 Z" fill="#4FD1A0"/>
<circle cx="36" cy="12" r="5" fill="#FFFFFF"/></svg>'''
def logo(w, h):
    s = h / 40.0
    return '''<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 160 40">
<g transform="translate(2,4) scale(0.44)">%s</g>
<text x="40" y="18" font-family="Inter" font-weight="600" font-size="13" fill="#FFFFFF">Second Opinion</text>
<text x="40" y="33" font-family="Inter" font-weight="400" font-size="12" fill="#C9D3E0">Triage · HF</text></svg>''' % (w, h, ALT.split('>',1)[1].rsplit('</svg>',1)[0])
for name, svg, size in (("appIcon", FILL, 36), ("appIcon_2x", FILL, 72), ("appIconAlt", ALT, 36), ("appIconAlt_2x", ALT, 72)):
    cairosvg.svg2png(bytestring=svg.encode(), write_to="static/%s.png" % name, output_width=size, output_height=size)
cairosvg.svg2png(bytestring=logo(160, 40).encode(), write_to="static/appLogo.png", output_width=160, output_height=40)
cairosvg.svg2png(bytestring=logo(320, 80).encode(), write_to="static/appLogo_2x.png", output_width=320, output_height=80)
open("static/icon.svg","w").write(FILL)
