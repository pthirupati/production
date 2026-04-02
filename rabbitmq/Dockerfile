FROM rabbitmq:3.13-management

# Copy custom config
COPY rabbitmq.conf /etc/rabbitmq/rabbitmq.conf

# Management UI
EXPOSE 5672 15672

CMD ["rabbitmq-server"]

