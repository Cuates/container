# Image
FROM python:latest
ARG TIMEZONE_LOCATION
ENV TZ=$TIMEZONE_LOCATION

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Install freetds and odbc drivers
RUN apt-get update \
&& apt-get install -y unixodbc \
&& apt-get install -y unixodbc-dev \
&& apt-get install -y tdsodbc \
&& apt-get install -y freetds-bin \
&& apt-get install -y freetds-common \
&& apt-get install -y freetds-dev \
&& apt-get install -y vim \
&& apt-get install -y iputils-ping \
&& apt-get install -y net-tools \
&& apt-get install -y libpq-dev

# Copy freetds and odbc files for mssql connection
COPY freetds.conf /etc/freetds/
COPY odbc.ini /etc/
COPY odbcinst.ini /etc/

# Working directory
WORKDIR /usr/local/src/moviefeedwebservice

# Pip upgrade setup tools and wheel
RUN pip install --upgrade pip setuptools wheel

# Pip install pipenv
RUN pip install pipenv

# Pip upgrade pipenv
RUN pip install --upgrade pipenv

# Copy pip files to container
COPY Pipfile* .

# Pipenv install
RUN pipenv install

# Pipenv lock
RUN pipenv lock

# Pipenv install deploy and ignore pip file
RUN pipenv install --deploy --ignore-pipfile

# Copy all content from local directory to image
COPY . .

# Expose port
EXPOSE 4817

# Pipenv run gunicorn command
CMD ["pipenv", "run", "gunicorn", "--bind", "0.0.0.0:4817", "--workers", "20", "--threads", "25", "moviefeedwebservice:app"]