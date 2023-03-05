NginxProxyManager

* Dependency
  * Create [docker network](https://github.com/Cuates/container/tree/main/docker/command) to associate against if not already done so
    * If using Nginx Proxy Manager, then all docker containers will need to be on the same docker network to be able to see each other
  * Open port (80 and 443) through modem
  * Open port (80 and 443) through router
  * Open port (80 and 443) through firewall of machine

* Adding a proxy host
  * Details
    * Domain Name
      * Should have been created from a domain website of your choice
    * Scheme (http)
    * Forward Hostname / IP
      * docker network inspect command above from target docker container
      * can also use the docker container name
    * Forward Port
      * Enter port you opened for target docker container
    * Radio select Block Common Exploits
    * Leave everything else as default
  * Custom Locations
    * Leave everything as default initially unless you are adding base urls
    * Click button Add location
      * Define location
        * /base-url-name
      * Scheme
        * http
      * Forward Hostname / IP
        * docker network inspect command above from target docker container
      * Forward Port
        * Enter port you opened for target docker container
  * SSL
    * SSL Certificate
      * Request a new SSL Certificate
    * Radio select
      * Force SSL
      * HTTP/2 Support
      * HSTS Enabled
      * HSTS Subdomains
      * I Agree to the Let's Encrypt Terms of Service
      * Leave everything else as default
    * Email Address for Let's Encrypt
   * Advanced
    * Leave everything as default
  * Click button Save
* NOTE: [Arrs applications](https://github.com/Cuates/container/tree/main/docker/media)
  * Make sure to setup and include the base urls before you can access through the Nginx Proxy Manager container
