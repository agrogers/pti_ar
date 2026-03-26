{
    'name': 'PTI AR',
    'version': '18.0.1.0.0',
    'category': 'Uncategorized',
    'summary': 'PTI AR Module',
    'description': """
PTI AR
======
Custom module for PTI AR functionality.
    """,
    'author': '',
    'website': '',
    'license': 'LGPL-3',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/pti_ar_views.xml',
        'views/menu.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
