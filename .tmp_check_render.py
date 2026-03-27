from app import app
c = app.test_client()
h = c.get('/').get_data(as_text=True)
l = c.get('/login').get_data(as_text=True)
print('HOME_AVAILABILITY_OK', 'product-card__availability' in h)
print('HOME_CONSULTAR_PRESENT', 'Consultar' in h)
print('LOGIN_FOOTER_PRESENT', '<footer class="footer">' in l)
