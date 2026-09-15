# Mimics odoo/release.py (real file at odoo/odoo, branch 17.0, verified
# against raw.githubusercontent.com/odoo/odoo/17.0/odoo/release.py on
# 2026-09-15). Trimmed to the assignments checkbox's profile.py actually
# reads; the FINAL-is-a-Name quirk is preserved on purpose -- it's the whole
# reason profile.py can't use ast.literal_eval directly.
RELEASE_LEVELS = [ALPHA, BETA, RELEASE_CANDIDATE, FINAL] = ['alpha', 'beta', 'candidate', 'final']
RELEASE_LEVELS_DISPLAY = {ALPHA: ALPHA,
                          BETA: BETA,
                          RELEASE_CANDIDATE: 'rc',
                          FINAL: ''}

version_info = (17, 0, 0, FINAL, 0, '')
version = '.'.join(str(s) for s in version_info[:2]) + RELEASE_LEVELS_DISPLAY[version_info[3]] + str(version_info[4] or '') + version_info[5]
series = serie = major_version = '.'.join(str(s) for s in version_info[:2])
