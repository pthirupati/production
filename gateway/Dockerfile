# FixitLab — Production Nginx Gateway with SSL
FROM nginx:1.25-alpine

# Install curl for healthcheck
RUN apk add --no-cache curl

# Remove default config
RUN rm /etc/nginx/conf.d/default.conf

# Copy production nginx config
COPY nginx.prod.conf /etc/nginx/conf.d/default.conf

# Copy htpasswd for admin-protected routes
COPY .htpasswd /etc/nginx/.htpasswd

EXPOSE 80 443

CMD ["nginx", "-g", "daemon off;"]
