# gp_railway_mapa

Mapa visual do G.P. Railway (trilhos, pontes de Manzanita e suportes) como
**ymaps nativos**. Substitui o antigo `gp-railway`, que usava o `objectloader`
(spawn por script, limite de 900 entidades; o mapa tem 984 objetos).

* 984 objetos em 6 ymaps de ~600 m (`stream/gp_rail_*.ymap`), ~270 KB no total.
* Sem script, sem `objectloader`, sem limite de entidades.
* A via para os trens fica em `gp_railway_trilhos`.

## Origem da conversão

Gerado de `gprailway.xml`, `manzanita_bridges.xml` e `supportsfinal.xml`:

* rotação: pitch/roll/yaw em ordem ZXY convertida para quaternion (conjugado,
  como no CodeWalker). Convenção conferida com os dados do Mexico Expansion Project.
* 8 modelos sem nome conhecido ficam como `hash_XXXXXXXX` (formato do RAGE).
* rotação idêntica à do kibook/spooner (`toQuaternion`), conferida nos 984 objetos.
* `lodDist` 500 e flags `1572897` = 1572865 + 32 (**congelado**, como o spooner
  grava). Com `1572865` os trilhos ficavam soltos (dinâmicos) e se desalinhavam.

## Atenção

* Teste em jogo: perto de `-1938, -1608, 115` os trilhos devem aparecer. Se algum
  objeto vier torto (pontes de Manzanita, perto de `-1951, -1515, 113`), a
  convenção de rotação precisa de ajuste.
* Não inicie junto com o antigo `gp-railway` (objetos duplicados).
