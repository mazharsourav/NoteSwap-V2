from django.urls import path
from django.views.generic import RedirectView

from .views import accounts, dashboard, files, notes, notesolve, pages, premium, providers, social

urlpatterns = [
    # Pages
    path('', pages.home, name='home'),
    path('about/', pages.about_page, name='about'),
    path('terms/', pages.terms_of_use, name='terms_of_use'),
    path('help/', pages.help_center, name='help_center'),
    path('help/<slug:slug>/', pages.help_article, name='help_article'),
    path('ask/', pages.ask_question, name='ask_question'),
    path('feedback/', pages.send_feedback, name='send_feedback'),
    path('contact/', pages.contact_page, name='contact'),
    path('robots.txt', pages.robots_txt, name='robots_txt'),

    # Accounts (sign up / sign in / verification / password reset: allauth, under /accounts/)
    path('login/', RedirectView.as_view(pattern_name='account_login', query_string=True)),
    path('register/', RedirectView.as_view(pattern_name='account_signup', query_string=True)),
    path('logout/', accounts.logout_view, name='logout'),
    path('profile/', accounts.profile_view, name='profile'),
    path('edit-profile/', accounts.edit_profile, name='edit_profile'),
    path('user/<int:user_id>/', accounts.user_profile, name='user_profile'),
    path('search/', accounts.search_users, name='search_users'),

    # Subjects and notes (old topic pages redirect to their subject)
    path('subjects/', notes.subject_list, name='subject_list'),
    path('notes/search/', notes.search, name='search'),
    path('add-subject/', notes.add_subject, name='add_subject'),
    path('subject/<int:subject_id>/', notes.subject_detail, name='subject_detail'),
    path('subject/<int:subject_id>/topics/', notes.old_subject_topics),
    path('topic/<int:topic_id>/notes/', notes.old_topic_notes),
    path('upload/', notes.upload_note, name='upload_note'),
    path('note/<int:note_id>/', notes.note_detail, name='note_detail'),
    path('note/<int:note_id>/edit/', notes.edit_note, name='edit_note'),
    path('note/<int:note_id>/delete/', notes.delete_note, name='delete_note'),
    path('note/<int:note_id>/resubmit/', notes.resubmit_note, name='resubmit_note'),
    path('note/<int:note_id>/files/', notes.note_files, name='note_files'),
    path('note/<int:note_id>/files/<int:file_id>/delete/', notes.delete_note_file, name='delete_note_file'),
    path('note/<int:note_id>/comment/', notes.comment_on_note, name='comment_on_note'),
    path('note/<int:note_id>/rate/', notes.rate_note, name='rate_note'),
    path('verify/', notes.verify_notes, name='verify_notes'),

    # Providers and provider applications
    path('providers/', providers.providers, name='providers'),
    path('provider/<int:provider_id>/', providers.provider_profile, name='provider_profile'),
    path('become-provider/', providers.become_provider, name='become_provider'),
    path('provider-requests/', providers.provider_requests, name='provider_requests'),
    # The detail route must come first: '<str:action>' would otherwise also match 'view'.
    path('provider-requests/<int:request_id>/view/', providers.provider_request_detail, name='provider_request_detail'),
    path('provider-requests/<int:request_id>/<str:action>/', providers.provider_request_action,
         name='provider_request_action'),

    # Following providers and notifications
    path('following/', social.following, name='following'),
    path('provider/<int:provider_id>/follow/', social.follow_provider, name='follow_provider'),
    path('provider/<int:provider_id>/unfollow/', social.unfollow_provider, name='unfollow_provider'),
    path('notifications/', social.notifications, name='notifications'),

    # NoteSolve
    path('notesolve/', notesolve.notesolve_dashboard, name='notesolve_dashboard'),
    path('notesolve/request/<int:provider_id>/', notesolve.request_to_provider, name='request_to_provider'),
    path('notesolve/requests/<int:request_id>/resend/', notesolve.resend_solve_request, name='resend_solve_request'),
    path('solve-request/<int:request_id>/', notesolve.solve_request_view, name='solve_request'),
    path('solved-requests/', notesolve.provider_solved_requests, name='provider_solved_requests'),

    # Premium
    path('premium/', premium.premium_packages, name='premium_packages'),
    path('premium/add/', premium.add_premium_package, name='add_premium_package'),
    path('premium/edit/<int:package_id>/', premium.edit_premium_package, name='edit_premium_package'),
    path('premium/delete/<int:package_id>/', premium.delete_premium_package, name='delete_premium_package'),
    path('premium/toggle/<int:package_id>/', premium.toggle_premium_package, name='toggle_premium_package'),
    path('premium/purchase/<int:package_id>/', premium.purchase_premium_package, name='purchase_premium_package'),
    path('premium/checkout/pending/', premium.checkout_pending, name='checkout_pending'),
    path('premium/approve/<int:purchase_id>/', premium.approve_purchase, name='approve_purchase'),
    path('premium/reject/<int:purchase_id>/', premium.reject_purchase, name='reject_purchase'),

    # Manage dashboard (moderators and superusers)
    path('manage_dash/', dashboard.manage_dash_view, name='Manage'),
    path('manage/inbox/', dashboard.inbox, name='inbox'),
    path('manage/premium/', dashboard.manage_premium, name='manage_premium'),
    path('manage/inbox/<int:message_id>/toggle/', dashboard.inbox_toggle, name='inbox_toggle'),

    # Protected file downloads (access-checked; never served from public /media/)
    path('files/notes/<int:note_id>/', files.note_file, name='note_file'),
    path('files/notes/extra/<int:file_id>/', files.note_extra_file, name='note_extra_file'),
    path('files/notes/<int:note_id>/all.zip', files.note_zip, name='note_zip'),
    path('files/notesolve/<int:file_id>/', files.notesolve_file, name='notesolve_file'),
    path('files/notesolve/solutions/<int:solution_id>/', files.notesolve_solution_file,
         name='notesolve_solution_file'),
]
