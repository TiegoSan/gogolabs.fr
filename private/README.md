# Espace privé GogoLabs

Le site public `gogolabs.fr` reste hébergé par GitHub Pages.

`/private/` sert seulement de point d'entrée depuis le site public et redirige vers :

```text
https://analytics.gogolabs.fr/
```

Le dashboard réel vit dans le repo privé `TiegoSan/gogolabs-analytics`, déployé via Cloudflare Pages et protégé par Cloudflare Access.

Ne pas commiter de payload App Store Connect dans ce repo public.
