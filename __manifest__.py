{
    'name': 'PTI - Parent Teacher Interviews',
    'version': '18.0.1.0.0',
    'category': 'Education',
    'summary': 'Manage Parent-Teacher Interview cycles, time slots, and meeting bookings',
    'description': """
PTI - Parent Teacher Interviews
================================
A comprehensive Odoo 18 module for managing Parent-Teacher Interview (PTI) sessions.

Features
--------
* **Meeting Cycles**: Define interview periods with default slot durations and times.
* **Time Slots**: Generate and manage individual interview time slots within a cycle.
* **Meetings**: Schedule and track meetings between parents, teachers, and students.
* **Bookings**: Allow parents and teachers to book available time slots.

Security Roles
--------------
* **PTI Manager**: Full access — create and manage cycles, slots, and meetings.
* **PTI Teacher**: View cycles/slots; create and manage meetings they are part of.
* **PTI Parent**: View available slots and manage their own bookings.
    """,
    'author': '',
    'website': '',
    'license': 'LGPL-3',
    'depends': ['base'],
    'data': [
        'security/pti_security.xml',
        'security/ir.model.access.csv',
        'views/dashboard_views.xml',
        'views/meeting_cycle_views.xml',
        'views/meeting_cycle_time_slot_views.xml',
        'views/partner_meeting_views.xml',
        'views/meeting_member_views.xml',
        'views/partner_time_slot_views.xml',
        'views/schedule_meetings_views.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pti_ar/static/src/components/search_dropdown.js',
            'pti_ar/static/src/components/search_dropdown.xml',
            'pti_ar/static/src/dashboard/pti_dashboard.js',
            'pti_ar/static/src/dashboard/pti_dashboard.xml',
            'pti_ar/static/src/dashboard/pti_dashboard.scss',
            'pti_ar/static/src/schedule_meetings/schedule_meetings.js',
            'pti_ar/static/src/schedule_meetings/schedule_meetings.xml',
            'pti_ar/static/src/schedule_meetings/schedule_meetings.scss',
        ],
    },
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}
