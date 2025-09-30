# Decisões Atuais

Este documento registra as decisões vigentes e o estado atual do comportamento da aplicação.

## TGFCAB – Gravação de Cabeçalho
- NUNOTA: gerado automaticamente. Estratégia: usar sequência candidata (ou avançar além do MAX existente) e retry em colisão de PK.
- DTALTER: preenchido com SYSDATE no INSERT quando obrigatório.
- HRMOV: preenchido automaticamente quando vier vazio/zero.
- NUMNOTA: se NOT NULL, usar 0 como placeholder quando não informado.
- TOP/TIPMOV: `DHTIPOPER` alinhado ao último `DHALTER` do `TGFTOP`, e `TIPMOV` coerente com o TOP.
- TPV: quando TIPMOV em (P, V, D), alinhar `DHTIPVENDA` ao último `DHALTER` do `TGFTPV`.
- Códigos opcionais conforme base:
  - CODVEND: permitido 0.
  - CODPARCTRANSP: opcional.
  - CODPROJ: opcional.
- Validações ativas: empresa ativa, natureza ativa e analítica, centro de custos analítico/ativo, regras de transferência (UTILIZALOCAL), limites de ano (TSIPAR) quando aplicável.

## UI – Central de Compras
- Typeahead: Parceiro, TOP, Natureza, CENCUS.
- Typeahead adicionais: Vendedor e Transportadora (ativos). Vendedor aceita 0; Transportadora opcional.
- Normalização de POST para evitar `int(list)`.
- Exibição de SQL + binds do plano para depuração.

## Triggers
- Exportadas para `sankhya_integration/triggers/triggers/`.
- Índice em `sankhya_integration/triggers/INDEX.md`.
- Comandos de management não rodam system checks para evitar dependências desnecessárias.

## Flags/Config
- `WRITE_ENABLED`: ativo para permitir gravação assistida.

---
Última atualização: 2025-09-22.
