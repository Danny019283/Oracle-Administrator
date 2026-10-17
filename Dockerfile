FROM container-registry.oracle.com/database/express:21.3.0-xe

# cargar argumento del .env
ARG ORACLE_PWD_ARG

# cargar variable de entorno
ENV ORACLE_PWD=${ORACLE_PWD_ARG}
ENV ORACLE_CHARACTERSET=AL32UTF8

# Puertos expuestos
EXPOSE 1521 5500
