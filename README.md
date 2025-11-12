# Streamplus Premium Hub – AI Chatbot Website (Django)

**Author & Developer:** Bryan Carl C. Mationg  
**GitHub:** [@bryancarl23](https://github.com/bryancarl23)

Run locally:

 ```bash
 python -m venv .venv && source .venv/bin/activate
 pip install -r requirements.txt
 python manage.py migrate
 python manage.py runserver
 ```

 Optional: configure environment in `.env`:

 ```env
 DJANGO_SECRET_KEY=replace-me
 GOOGLE_API_KEY=AIzaSyD_yIm5zuEV3XE6nNnvl81Ofo4q4Ki8VFg
 ```

 Pages: `/`, `/about/`, `/products/`, `/marketing/`, `/contact/`

 Chatbot: floating widget bottom-right. Endpoint: `POST /chatbot/` with `{ "message": "..." }`.



