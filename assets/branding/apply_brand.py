#!/usr/bin/env python3
"""Apply Snowflake branding to a sizing HTML file.

Usage:
    python assets/branding/apply_brand.py <input.html> [output.html]

If output.html is omitted, the input file is modified in place.
"""
import sys
import re
import os

HERE = os.path.dirname(os.path.abspath(__file__))

def load(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def build_logo_tag(logo_svg):
    """Wrap logo SVG with height=36, remove fixed width."""
    svg = re.sub(r'<svg ([^>]*?)width="[^"]*"([^>]*?)height="[^"]*"', r'<svg \1height="36"\2', logo_svg, count=1)
    svg = re.sub(r'<svg ([^>]*?)height="[^"]*"([^>]*?)width="[^"]*"', r'<svg \1height="36"\2', svg, count=1)
    if 'height="36"' not in svg[:200]:
        svg = svg.replace('<svg ', '<svg height="36" ', 1)
    return f'<div style="height:36px;display:flex;align-items:center;">\n      {svg.strip()}\n    </div>'

def build_mark_svg(mark_svg):
    """Prepare the official Snowflake crystal mark SVG for inline use at height=20."""
    svg = re.sub(r'<\?xml[^?]*\?>\s*', '', mark_svg)
    svg = re.sub(r'<!DOCTYPE[^>]*>\s*', '', svg)
    svg = re.sub(r'<metadata>.*?</metadata>\s*', '', svg, flags=re.DOTALL)
    # Change black fill to brand blue
    svg = svg.replace('fill="#000000"', 'fill="#29B5E8"')
    # Strip width/height attrs from root <svg> tag (they use "pt" units)
    svg = re.sub(r'\s+width="[^"]*"', '', svg, count=1)
    svg = re.sub(r'\s+height="[^"]*"', '', svg, count=1)
    # Inject height=20 and inline style
    svg = svg.replace('<svg', '<svg height="20" style="vertical-align:middle;margin-right:6px;"', 1)
    return svg.strip()

def apply_brand(html, fonts_css, logo_svg, favicon_b64, mark_svg):
    # 1. Remove Google Fonts link
    html = re.sub(r'\s*<link [^>]*fonts\.googleapis\.com[^>]*>\n?', '\n', html)

    # 2. Replace any existing favicon with the official PNG favicon
    #    (handles both fresh files and re-runs with old hand-drawn favicon)
    html = re.sub(r'<link rel="icon"[^>]*>\n?', '', html)
    favicon = f'<link rel="icon" type="image/x-icon" href="data:image/x-icon;base64,{favicon_b64}">'
    html = html.replace('</head>', f'{favicon}\n</head>', 1)

    # 3. Inject brand fonts CSS at the very start of the <style> block
    #    Skip if already present (re-run safety)
    if '/* === Snowflake Brand Fonts' not in html:
        brand_font_block = f'/* === Snowflake Brand Fonts (base64 inlined) === */\n{fonts_css}\n/* === End Brand Fonts === */\n'
        html = re.sub(r'(<style>)\s*\n', r'\1\n' + brand_font_block.replace('\\', '\\\\'), html, count=1)

    # 4. Replace :root CSS block
    new_root = """:root {
  /* Primary brand — sourced from snowflake.com canonical tokens */
  --sf-blue:      #29B5E8;
  --sf-blue-dark: #249EDC;
  --sf-navy:      #11567F;
  --sf-navy-deep: #003545;
  --sf-sky:       #76D0F1;
  --sf-teal:      #76D0F1;
  --sf-orange:    #FF9F36;
  --sf-surface:   #ECF1F5;
  --sf-divider:   #A0BBCC;
  --gray-800: #2d3748;
  --gray-700: #4a5568;
  --gray-600: #718096;
  --gray-200: #e2e8f0;
  --gray-100: #f7fafc;
  --white: #ffffff;
  --success: #38a169;
  --warning: #ED7D31;
}"""
    html = re.sub(r':root\s*\{[^}]+\}', new_root, html, count=1)

    # 5. Update body font-family: Open Sans → Lato
    html = re.sub(
        r"font-family:\s*'Open Sans'[^;]+;",
        "font-family: 'Lato', -apple-system, BlinkMacSystemFont, sans-serif;",
        html
    )

    # 6. Update header gradient
    html = html.replace(
        'linear-gradient(135deg, var(--sf-navy-deep) 0%, #0d3a5f 100%)',
        'linear-gradient(140.86deg, var(--sf-navy-deep) 0%, var(--sf-navy) 100%)'
    )

    # 7. Add Texta font to h1 in header (and .kpi-value, .scenario-tcv)
    if '.header h1' in html:
        html = html.replace(
            '.header h1 { margin: 0; font-size: 36px; font-weight: 700; }',
            ".header h1 { margin: 0; font-size: 36px; font-weight: 700; font-family: 'Texta', 'Lato', sans-serif; }"
        )
    html = re.sub(
        r'(\.section h2\s*\{[^}]*?)(\})',
        lambda m: m.group(1) + " font-family: 'Texta', 'Lato', sans-serif;" + m.group(2),
        html, count=1
    )

    # 8. Update workload-calc font to Source Code Pro
    html = re.sub(
        r'(\.workload-calc\s*\{[^}]*?)(\})',
        lambda m: m.group(1).replace('monospace', "'Source Code Pro', monospace") + m.group(2)
        if 'monospace' in m.group(1)
        else m.group(1) + " font-family: 'Source Code Pro', monospace;" + m.group(2),
        html, count=1
    )

    # 9. Update KPI value font
    html = re.sub(
        r'(\.kpi-value\s*\{[^}]*?)(\})',
        lambda m: m.group(1) + " font-family: 'Texta', 'Lato', sans-serif;" + m.group(2),
        html, count=1
    )

    # 10. Replace the fake Snowflake logo SVG in the header with the real one
    logo_tag = build_logo_tag(logo_svg)
    html = re.sub(
        r'<svg\s+width="(?:180|140)"\s+height="(?:36|32)"[^>]*>.*?</svg>',
        logo_tag,
        html,
        count=1,
        flags=re.DOTALL
    )

    # 11. Replace chart segment colors — only on files missing the palette constant.
    #     On re-runs (const already defined) just fix any self-reference; skip replacements
    #     so the palette's own '#29B5E8' literal doesn't get clobbered.
    if 'const SF_CHART_PALETTE' not in html:
        html = html.replace("'#8B5CF6'", "SF_CHART_PALETTE[2]")
        html = html.replace('"#8B5CF6"', "SF_CHART_PALETTE[2]")
        html = html.replace("'#F59E0B'", "SF_CHART_PALETTE[3]")
        html = html.replace('"#F59E0B"', "SF_CHART_PALETTE[3]")
        html = html.replace("'#29B5E8'", "SF_CHART_PALETTE[0]")
        html = html.replace('"#29B5E8"', "SF_CHART_PALETTE[0]")
        html = html.replace("'#00C8D7'", "SF_CHART_PALETTE[1]")
        html = html.replace('"#00C8D7"', "SF_CHART_PALETTE[1]")
        html = html.replace("'#718096'", "SF_CHART_PALETTE[4]")
        html = html.replace('"#718096"', "SF_CHART_PALETTE[4]")
        html = html.replace("'var(--sf-blue)'", "SF_CHART_PALETTE[0]")
        html = html.replace('"var(--sf-blue)"', "SF_CHART_PALETTE[0]")
        html = html.replace("'var(--sf-teal)'", "SF_CHART_PALETTE[1]")
        html = html.replace('"var(--sf-teal)"', "SF_CHART_PALETTE[1]")
        html = html.replace("'var(--gray-600)'", "SF_CHART_PALETTE[4]")
        html = html.replace('"var(--gray-600)"', "SF_CHART_PALETTE[4]")
    else:
        # Re-run: fix broken palette self-reference if present (old apply_brand.py bug)
        html = re.sub(
            r"const SF_CHART_PALETTE\s*=\s*\[[^\]]*SF_CHART_PALETTE\[0\][^\]]*\];",
            "const SF_CHART_PALETTE = ['#11567F', '#1B7BAE', '#29B5E8', '#76D0F1', '#A0BBCC'];",
            html
        )

    # 12. NOW inject SF_CHART_PALETTE constant (after color replacements so its literals stay clean)
    if 'const SF_CHART_PALETTE' not in html:
        palette_line = "const SF_CHART_PALETTE = ['#11567F', '#1B7BAE', '#29B5E8', '#76D0F1', '#A0BBCC'];\n\n"
        if 'const WH_CREDITS' in html:
            html = html.replace('const WH_CREDITS', palette_line + 'const WH_CREDITS')
        elif '<script>' in html:
            html = html.replace('<script>', '<script>\n' + palette_line, 1)

    # 13. Update footer: replace any existing mark SVG (hand-drawn or real) and add
    #     "Snowflake Confidential" if not already present.
    real_mark = build_mark_svg(mark_svg)

    # Case A: footer already has the branded <div style="margin-bottom:8px;"> block
    #         — replace whatever SVG mark is in it (hand-drawn or previous crystal mark)
    if '<div style="margin-bottom:8px;">' in html:
        html = re.sub(
            r'(<div style="margin-bottom:8px;">)\s*<svg.*?</svg>',
            r'\1\n    ' + real_mark.replace('\\', '\\\\'),
            html,
            flags=re.DOTALL,
            count=1
        )
    else:
        # Case B: original unbranded footer — inject the mark div before the first <p>
        old_footer = ('<div class="footer">\n'
                      '  <p>Prepared by Snowflake')
        new_footer = (f'<div class="footer">\n'
                      f'  <div style="margin-bottom:8px;">\n'
                      f'    {real_mark}\n'
                      f'    <span style="font-weight:700;">Snowflake Confidential</span>\n'
                      f'  </div>\n'
                      f'  <p>Prepared by Snowflake')
        if old_footer in html:
            html = html.replace(old_footer, new_footer, 1)
        elif 'Snowflake Confidential' not in html:
            # Case C: different footer structure — prepend mark div after opening tag
            html = re.sub(
                r'(<div class="footer">)\s*\n',
                r'\1\n  <div style="margin-bottom:8px;">\n    ' + real_mark.replace('\\', '\\\\') + r'\n    <span style="font-weight:700;">Snowflake Confidential</span>\n  </div>\n',
                html, count=1
            )

    return html


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else input_path

    fonts_css  = load(os.path.join(HERE, '_brand_fonts.css'))
    logo_svg   = load(os.path.join(HERE, '_brand_logo.svg'))
    favicon_b64 = load(os.path.join(HERE, '_brand_favicon.b64')).strip()
    mark_svg   = load(os.path.join(HERE, 'snowflake-mark.svg'))
    html = load(input_path)

    branded = apply_brand(html, fonts_css, logo_svg, favicon_b64, mark_svg)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(branded)

    orig_kb = len(html.encode()) // 1024
    new_kb = len(branded.encode()) // 1024
    print(f"Branded: {input_path} → {output_path}  ({orig_kb}KB → {new_kb}KB)")


if __name__ == '__main__':
    main()
