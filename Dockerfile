FROM python:3.9
COPY ./pyproject.toml /code/pyproject.toml
RUN pip install poetry
RUN poetry config virtualenvs.create false

WORKDIR /code

RUN poetry install
RUN poetry add mysqlclient
COPY ./__init__.py ./__init__.py
COPY ./main.py ./main.py


ENTRYPOINT [ "python", "main.py" ]
