from gaesessions import SessionMiddleware
def webapp_add_wsgi_middleware(app):
    return SessionMiddleware(app, cookie_key="0Rly?HAWACHA Think?!This is teh bongo biscuit.....Eh?")