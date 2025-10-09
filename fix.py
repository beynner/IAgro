import sys

FILE = r'c:\Users\Semear\Documents\Packing_House\sankhya_integration\templates\sankhya_integration\comercial_dashboard.html'

print("Reading file...")
with open(FILE, 'r', encoding='utf-8') as f:
    content = f.read()

changes = 0

# Fix 1
old1 = '''                  <colgroup>
                    <col />
                    <col style="width:90px" />
                    <col style="width:110px" />
                    <col style="width:110px" />
                    <col style="width:80px" />
                  </colgroup>
                  <thead>
                    <tr style="background:#f8fafb; border-bottom:1px solid #e5e7eb;">
                      <th style="text-align:left; padding:6px 8px; font-size:.85rem; color:#334155;">Produto</th>
                      <th style="text-align:right; padding:6px 8px; font-size:.85rem; color:#334155;">Qtde</th>
                      <th style="text-align:right; padding:6px 8px; font-size:.85rem; color:#334155;">Valor Inicial</th>
                      <th style="text-align:right; padding:6px 8px; font-size:.85rem; color:#334155;">Valor Total</th>
                      <th style="text-align:left; padding:6px 8px; font-size:.85rem; color:#334155;">Status</th>
                      <th style="text-align:right; padding:6px 8px; font-size:.85rem; color:#334155;">Ação</th>
                    </tr>
                  </thead>
                  <tbody id="valeClassBody">'''

new1 = '''                  <colgroup>
                    <col />
                    <col style="width:90px" />
                    <col style="width:110px" />
                    <col style="width:110px" />
                    <col style="width:110px" />
                    <col style="width:80px" />
                  </colgroup>
                  <thead>
                    <tr style="background:#f8fafb; border-bottom:1px solid #e5e7eb;">
                      <th style="text-align:left; padding:6px 8px; font-size:.85rem; color:#334155;">Produto</th>
                      <th style="text-align:right; padding:6px 8px; font-size:.85rem; color:#334155;">Qtde</th>
                      <th style="text-align:right; padding:6px 8px; font-size:.85rem; color:#334155;">Valor Inicial</th>
                      <th style="text-align:right; padding:6px 8px; font-size:.85rem; color:#334155;">Valor Final</th>
                      <th style="text-align:right; padding:6px 8px; font-size:.85rem; color:#334155;">Valor Total</th>
                      <th style="text-align:left; padding:6px 8px; font-size:.85rem; color:#334155;">Status</th>
                      <th style="text-align:right; padding:6px 8px; font-size:.85rem; color:#334155;">Ação</th>
                    </tr>
                  </thead>
                  <tbody id="valeClassBody">'''

if old1 in content:
    content = content.replace(old1, new1, 1)
    changes += 1
    print("OK Fix 1")
else:
    print("FAIL Fix 1")

# Fix 2    
old2 = """              const vlrtot = Number(r.vlrtot||0) || 0;
              // Usar VLRTOT salvo (valor da distribuição) em vez de calcular com preço inicial
              const totalIni = vlrtot;"""

new2 = """              const vlrtot = Number(r.vlrtot||0) || 0;
              const vlrunit = Number(r.vlrunit||0) || 0;
              // Usar VLRTOT salvo (valor da distribuição) em vez de calcular com preço inicial
              const totalIni = vlrtot;"""

if old2 in content:
    content = content.replace(old2, new2, 1)
    changes += 1
    print("OK Fix 2a")
else:
    print("FAIL Fix 2a")

# Fix 3
old3 = """                </a>` : '';
              return `<tr data-q="${qnum}" data-unit="${unit}" data-nun="${nun}" data-seq="${seq}">"""

new3 = """                </a>` : '';
              const cifrao = `<span style="color:#9ca3af;opacity:0.7;font-size:0.8em;margin-right:2px;">R$</span>`;
              return `<tr data-q="${qnum}" data-unit="${unit}" data-nun="${nun}" data-seq="${seq}">"""

if old3 in content:
    content = content.replace(old3, new3, 1)
    changes += 1
    print("OK Fix 3")
else:
    print("FAIL Fix 3")

# Fix 4
old4 = """                <td style="padding:6px 8px; border-bottom:1px solid #e5e7eb; text-align:right;"><input class="vcl-preco-inicial" data-nun="${nun}" data-seq="${seq}" type="text" inputmode="decimal" style="width:90px; text-align:right; padding:0; border:none; background:transparent;" value="${precoIni?fmtMoney(precoIni):''}" placeholder="R$" /></td>
                <td style="padding:6px 8px; border-bottom:1px solid #e5e7eb; text-align:right;">${fmtMoney(totalIni)}</td>"""

new4 = """                <td style="padding:6px 8px; border-bottom:1px solid #e5e7eb; text-align:right;">${cifrao}<input class="vcl-preco-inicial" data-nun="${nun}" data-seq="${seq}" type="text" inputmode="decimal" style="width:70px; text-align:right; padding:0; border:none; background:transparent; display:inline-block;" value="${precoIni?(precoIni.toFixed(2)):''}" placeholder="0,00" /></td>
                <td style="padding:6px 8px; border-bottom:1px solid #e5e7eb; text-align:right;">${vlrunit>0?cifrao+(vlrunit.toFixed(2)):'—'}</td>
                <td style="padding:6px 8px; border-bottom:1px solid #e5e7eb; text-align:right;">${fmtMoney(totalIni)}</td>"""

if old4 in content:
    content = content.replace(old4, new4, 1)
    changes += 1
    print("OK Fix 4")
else:
    print("FAIL Fix 4")

if changes >= 4:
    with open(FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"SUCCESS! Applied {changes}/4 fixes")
else:
    print(f"ERROR: Only {changes}/4 fixes applied")
    sys.exit(1)
