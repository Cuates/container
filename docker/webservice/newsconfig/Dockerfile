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
&& apt-get install -y build-essential \
&& apt-get install -y python3-dev \
&& apt-get install -y vim \
&& apt-get install -y iputils-ping \
&& apt-get install -y net-tools \
&& apt-get install -y libpq-dev

# Microsoft SQL Server ODBC Driver 18 setup
RUN apt-get update && apt-get install -y curl gnupg apt-transport-https

# Add Microsoft package signing key securely
RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor | tee /etc/apt/trusted.gpg.d/microsoft.gpg > /dev/null

# Add Microsoft SQL Server repo for Debian 12
RUN echo "deb [signed-by=/etc/apt/trusted.gpg.d/microsoft.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql-release.list

# Install ODBC driver
RUN apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql18

# Optional cleanup
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy freetds and odbc files for mssql connection
# Make sure to update the odbcinit.ini file path for "ODBC Driver for SQL Server" as the driver could have updated
COPY freetds.conf /etc/freetds/
COPY odbc.ini /etc/
COPY odbcinst.ini /etc/

# Working directory
WORKDIR /usr/local/src/newsfeedwebservice

# Pip upgrade setup tools and wheel
RUN pip install --upgrade pip setuptools wheel

RUN pip install pyodbc

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
EXPOSE 4815

# Pipenv run uvicorn command
CMD ["pipenv", "run", "uvicorn", "--host", "0.0.0.0", "--port", "4815", "--workers", "20", "newsfeedwebservice:app"]
