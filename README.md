

- `cp .env.example .env`
- edit .env with your DSN and SA JSON path
- `export $(grep -v '^#' .env | xargs -0 -I{} echo {} | tr '\n' ' ')`
- `make install`
- `make test`
- `make etl`
