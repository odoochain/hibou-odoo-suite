FROM hibou/hibou-odoo:11.0

USER 0
RUN pip install redis==3.2.1 minio==4.0.18

USER 104
COPY --chown=104 . /opt/odoo/hibou-suite
RUN rm /etc/odoo/odoo.conf \
    && cp /opt/odoo/hibou-suite/debian/odoo.conf /etc/odoo/odoo.conf \
    ;

