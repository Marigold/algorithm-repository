FROM hbpmip/r-linear-regression

COPY testthat.R /src/tests/
COPY testthat/ /src/tests/testthat/

WORKDIR /src

ENTRYPOINT ["/usr/bin/Rscript", "/src/tests/testthat.R"]
