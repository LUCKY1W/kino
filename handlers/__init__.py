from . import start, admin_panel, upload_movie, manage_admins, manage_channels, statistics, broadcast

def register_all_handlers(dp):
    start.register(dp)
    admin_panel.register(dp)
    upload_movie.register(dp)
    manage_admins.register(dp)
    manage_channels.register(dp)
    statistics.register(dp)
    broadcast.register(dp)
