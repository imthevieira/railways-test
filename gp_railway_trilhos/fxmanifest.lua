fx_version 'cerulean'
game 'rdr3'
rdr3_warning 'I acknowledge that this is a prerelease build of RedM, and I am aware my resources *will* become incompatible once RedM ships.'

author 'G.P. Railway'
description 'G.P. Railway || Via férrea funcional (substitui o traintracks.xml do jogo)'
version '2.0.0'

-- ATENÇÃO: replace_traintrack_file SUBSTITUI toda a malha ferroviária do jogo
-- (citizenfx/fivem#2624). Apenas um resource pode usá-lo por vez. Qualquer via
-- customizada nova deve ser adicionada ao traintracks.xml deste resource.
-- Não use hífens no nome da pasta nem nos caminhos.
replace_traintrack_file 'traintracks.xml'

files {
	'traintracks.xml',
	'data/gp_railway.dat',
}
