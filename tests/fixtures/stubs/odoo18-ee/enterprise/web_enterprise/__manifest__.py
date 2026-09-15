# Mimics enterprise/web_enterprise/__manifest__.py. Real Odoo Enterprise is a
# private repo this project has no access to, so the exact manifest body is
# not independently verifiable; the technical name and its absence from the
# Community monorepo ARE verified (404 at
# raw.githubusercontent.com/odoo/odoo/18.0/addons/web_enterprise/, checked
# 2026-09-15; corroborated by odoo.com/forum threads on Enterprise activation
# naming this module). Used only as the edition-detection signal in
# profile.py's _find_web_enterprise(); the manifest body itself is invented
# for the stub and carries no independent evidence.
{
    'name': 'Enterprise Web',
    'category': 'Hidden',
    'depends': ['web'],
    'installable': True,
    'license': 'OEEL-1',
}
