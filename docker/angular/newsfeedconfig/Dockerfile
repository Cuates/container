# Stage 1: Compile and Build angular codebase

# Use official node image as the base image
FROM node:latest as build

# Set the working directory
WORKDIR /usr/local/app

# Clear npm cache
# RUN npm cache clean --force
RUN yarn cache clean --force

# Add the source code to app
COPY ./ /usr/local/app/

# Install all the dependencies
# RUN npm install
RUN yarn

# Generate the build of the application
# RUN npm run build --configuration=production
RUN yarn run build --configuration=production

# Stage 2: Serve app with nginx server

# Use official nginx image as the base image
FROM nginx:latest
ARG TIMEZONE_LOCATION
ENV TZ=$TIMEZONE_LOCATION

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Remove the default nginx config file from the Docker image
RUN rm /etc/nginx/conf.d/default.conf

# Copy the nginx.conf file from the host machine to the Docker image to configure Nginx to host the Angular application
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy the build output to replace the default nginx contents.
COPY --from=build /usr/local/app/dist/angularnewsfeed /usr/share/nginx/html

# Exposing a port, here it means that inside the container
# the app will be using Port 80 while running
EXPOSE ${NGNF_EXTERNAL_PORT}
