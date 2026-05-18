# Self-host Umami on Railway for gogolabs.fr

This directory is a Railway-ready Umami service. Railway runs the Umami
container, Railway PostgreSQL stores the analytics data, and Railway handles
HTTPS/custom-domain routing for `stats.gogolabs.fr`.

## Railway setup

Umami's official Railway guide also recommends Railway as the quickest hosted
self-host path:

https://docs.umami.is/docs/guides/running-on-railway

Use this repo-based setup if you want the deployment config versioned with the
GogoLabs website.

1. In Railway, create a new project.

2. Add a PostgreSQL database service:

   ```txt
   New -> Database -> Add PostgreSQL
   ```

3. Add an Umami service from this GitHub repo.

4. Set the service root directory to:

   ```txt
   deploy/umami
   ```

5. Add the variables from `.env.example` to the Umami service variables.

   `DATABASE_URL` should reference Railway's PostgreSQL service:

   ```txt
   DATABASE_URL=${{Postgres.DATABASE_URL}}
   ```

6. Replace `APP_SECRET` with a long random value:

   ```sh
   openssl rand -base64 48
   ```

7. Deploy the Umami service.

8. Open the Railway-generated domain and log in with:

   ```txt
   username: admin
   password: umami
   ```

9. Change the default password immediately.

10. In the Umami service settings, add the custom domain:

   ```txt
   stats.gogolabs.fr
   ```

11. Add the CNAME/TXT records Railway gives you in the DNS for `gogolabs.fr`.

12. Once Railway verifies the domain, open:

   ```txt
   https://stats.gogolabs.fr
   ```

13. Add `gogolabs.fr` as a website in Umami, then copy the tracking code.

14. Add the tracking script to the `<head>` of every HTML page in this repo.

The tracking code will look like this:

```html
<script
  defer
  src="https://stats.gogolabs.fr/script.js"
  data-website-id="YOUR-WEBSITE-ID"
></script>
```
