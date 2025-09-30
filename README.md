# PackingHouse

Projeto Django com integração Oracle (Sankhya) e páginas Portal/Central do Packing House (somente leitura).

## Requisitos
- Python 3.11+ (ou compatível com sua venv)
- Oracle Instant Client e rede configurada

## Setup (Windows PowerShell)
```powershell
# Na raiz do projeto
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py check
python manage.py runserver
```

## Rotas principais
- `/sankhya/` (index)
- `/sankhya/packing/portal/`
- `/sankhya/packing/central/`

## Observações
- Operações de Salvar/Excluir estão desabilitadas por política (read-only).
- O nome do projeto foi normalizado para `PackingHouse`.
- Para renomear a pasta raiz do workspace:
  1. Feche o VS Code e terminais que estejam em `D:\TI\NexusGTi\Harvest`.
  2. Execute:
     ```powershell
     Rename-Item -Path "D:\TI\NexusGTi\Harvest" -NewName "PackingHouse"
     ```
  3. Reabra o VS Code em `D:\TI\NexusGTi\PackingHouse` e ative a venv:
     ```powershell
     .\venv\Scripts\Activate.ps1
     python manage.py check
     ```

## Próximos passos (planejamento)
- Unificar campo Parceiro no Portal (feito): campo único com typeahead (código ou nome) e hidden `codparc`.
- Melhorias de UX dos typeaheads: navegação por teclado (↑/↓/Enter) e destaque (feito).
- Preencher resumo da Central com NUMNOTA, DTNEG, Parceiro e total (feito).
- Fluxo de Salvar/Excluir (a planejar):
   - Criar endpoints POST com CSRF e validações de negócio.
   - Confirmar ação em UI, exibindo resumo da operação.
   - Manter feature flag para liberar escrita somente quando autorizado.
