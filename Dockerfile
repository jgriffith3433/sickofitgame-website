# Use official nginx alpine image for smaller size
FROM nginx:alpine AS base

# Remove default nginx configuration
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost/health || exit 1

# Development target - for local development with volume mounts
FROM base AS development
# Files will be mounted via volumes in docker-compose.dev.yml
CMD ["nginx", "-g", "daemon off;"]

# Production target - for deployment with baked-in files
FROM base AS production

# Copy the Unity WebGL game files (includes Build/ and TemplateData/ subdirectories)
COPY Game/ /usr/share/nginx/html/Game/

# Copy the optimized index.html for full-screen experience
COPY index.html /usr/share/nginx/html/index.html

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
