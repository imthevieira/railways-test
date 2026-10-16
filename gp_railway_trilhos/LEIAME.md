# gp_railway_trilhos

Via férrea do mapa G.P. Railway (`[objectloader]/[maps]/gp-railway`, só props).

Usa `replace_traintrack_file` (citizenfx/fivem#2624): o `traintracks.xml` deste
resource substitui o do jogo. Ele contém as 29 vias vanilla (apontando para
`common:/data/levels/rdr3/`) mais a via `gp_railway`.

| Arquivo | Função |
|---|---|
| `fxmanifest.lua` | `replace_traintrack_file 'traintracks.xml'` e lista de `files` |
| `traintracks.xml` | Vias vanilla + `gp_railway` |
| `data/gp_railway.dat` | 382 nós (Bézier), laço **fechado** de ~3,8 km |
| `tools/gerar_trilho.py` | Gera o `.dat` a partir dos props do `gprailway.xml` |

## A via

* Trilhos reais: ~3,3 km, de `-1694.8, -1855.2, 81.9` até `-1666.5, -2240.1, 50.2`.
* O laço fecha com um conector de ~555 m **sem trilho visível** entre as pontas.
* Sem junções nem estações (flags `0`); não conecta à malha vanilla.
* Curvas apertadas (raio mínimo ~21 m) e declividade de até ~27 %.

## Regras

* **Reinicie o servidor inteiro** ao mudar trilhos. Recarregar a malha com trem
  existente derruba o jogo.
* Máximo de 50 vias no total (hoje: 30).
* Só um resource pode usar `replace_traintrack_file`. Não duplique em outro.
* Teste: fique sobre os trilhos (ex.: `-1938, -1608, 115`) e rode `/ghosttrain`.

## Regerar

```bash
python -I tools/gerar_trilho.py "../../[objectloader]/[maps]/gp-railway/stream/gprailway.xml" saida --close
```

Copie o `gp_railway.dat` gerado para `data/`. Ajuste a altura com `--z-offset 0.15`.
