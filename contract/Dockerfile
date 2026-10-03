FROM python:3.12-slim
WORKDIR /app
COPY contract/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY contract/ ./contract/
ENV PORT=8080
EXPOSE 8080
# Railway injects PORT. contract.serve binds a dual-stack socket on "::"
# (IPv4 + IPv6) so the service works over Railway private networking too.
# HOST=0.0.0.0 forces IPv4-only.
CMD ["python", "-m", "contract.serve"]
