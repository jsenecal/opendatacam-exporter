FROM python:3
RUN mkdir /opt/opendatacam_exporter
COPY *.py /opt/opendatacam_exporter/
COPY pyproject.toml /opt/opendatacam_exporter/
WORKDIR /opt/opendatacam_exporter/

ENV PYTHONPATH=${PYTHONPATH}:${PWD} 
RUN pip3 install poetry
RUN poetry config virtualenvs.create false
RUN poetry install --no-dev

EXPOSE 8000

CMD ["uvicorn", "exporter:app", "--host", "0.0.0.0", "--port", "8000"]