FROM nginx:1.25-alpine

# Remove default config
RUN rm /etc/nginx/conf.d/default.conf

# Copy our config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy htpasswd for admin-protected routes (MailHog, etc.)
COPY .htpasswd /etc/nginx/.htpasswd

# Expose HTTP
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

