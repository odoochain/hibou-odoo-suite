FROM hibou/hibou-odoo:14.0

USER 0
WORKDIR /opt/theia
COPY dev.package.json ./package.json
RUN set -x; \
        curl -sL https://deb.nodesource.com/setup_12.x | bash - \
        && apt-get install -y \
           nodejs \
           build-essential \
           libsecret-1-0 \
           procps \
        && npm install --global yarn
RUN     yarn --pure-lockfile && \
    NODE_OPTIONS="--max_old_space_size=4096" yarn theia build && \
    yarn theia download:plugins && \
    yarn --production && \
    yarn autoclean --init && \
    echo *.ts >> .yarnclean && \
    echo *.ts.map >> .yarnclean && \
    echo *.spec.* >> .yarnclean && \
    yarn autoclean --force && \
    yarn cache clean && \
    chown -R 104:33 /opt/theia \
    ;

USER 104
COPY --from=hibou/flow /flow /flow
COPY --chown=104 entrypoint.sh /entrypoint.sh
COPY --chown=104 . /opt/odoo/hibou-suite
RUN rm /etc/odoo/odoo.conf \
    && cp /opt/odoo/hibou-suite/debian/odoo.conf /etc/odoo/odoo.conf \
    ;

EXPOSE 3000
ENV SHELL=/bin/bash \
    THEIA_DEFAULT_PLUGINS=local-dir:/opt/theia/plugins
ENV USE_LOCAL_GIT true

