# Mimics addons/account/__manifest__.py (real file, branch 17.0).
# Trimmed: only present so purchase's 'depends': ['account'] resolves in
# fixtures that walk the dependency graph (P3+); not fetched/verified in
# full for P1, which only needs the manifest to exist and be parseable.
{
    'name': 'Accounting',
    'version': '1.1',
    'category': 'Accounting/Accounting',
    'depends': ['base'],
    'installable': True,
    'license': 'LGPL-3',
}
