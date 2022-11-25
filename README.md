# Celery AsyncIO Pool

![python](https://img.shields.io/pypi/pyversions/celery-aio-pool.svg)
![version](https://img.shields.io/pypi/v/celery-aio-pool.svg)
![downloads](https://img.shields.io/pypi/dm/celery-aio-pool.svg)
![format](https://img.shields.io/pypi/format/celery-aio-pool.svg)

<p align="center" width="100%">
    <img width="55%" src="https://raw.githubusercontent.com/the-wondersmith/celery-aio-pool/main/icon.svg">
</p>

> Free software: GNU Affero General Public License v3+

## Getting Started

### Installation

#### Using Poetry _(preferred)_

```
poetry add celery-aio-pool
```

#### Using `pip` & [PyPI.org](https://pypi.org/project/celery-aio-pool/)

```
pip install celery-aio-pool
```

#### Using `pip` & [GitHub](https://github.com/the-wondersmith/celery-aio-pool.git)

```
pip install git+https://github.com/the-wondersmith/celery-aio-pool.git
```

### Using `pip` & A Local Copy Of The Repo

```
git clone https://github.com/the-wondersmith/celery-aio-pool.git
cd celery-aio-pool
pip install -e "$(pwd)"
```


### Configure Celery

#### Using `celery-aio-pool`'s Provided Patcher _(non-preferred)_

- Import `celery_aio_pool` in the same module where your Celery "app" is defined
- Ensure that the `patch_celery_tracer` utility is called **_before_** any other
  Celery code is called

```python
"""My super awesome Celery app."""

# ...
from celery import Celery

# add the following import
import celery_aio_pool as aio_pool

# ensure the patcher is called *before*
# your Celery app is defined

assert aio_pool.patch_celery_tracer() is True

app = Celery(
    "my-super-awesome-celery-app",
    broker="amqp://guest@localhost//",
    # add the following keyword argument
    worker_pool=aio_pool.pool.AsyncIOPool,
)
```

#### Using (Upcoming) _Out-Of-Tree_ Worker Pool _(preferred)_

At the time of writing, [Celery](https://github.com/celery/celery) does not have
built-in support for out-of-tree pools like `celery-aio-pool`, but support should
be included starting with the first non-beta release of Celery 5.3. (note: [PR #7880](https://github.com/celery/celery/pull/7880) was merged on `2022-11-15`).

The official release of Celery 5.3 enables the configuration of custom worker pool classes thusly:

- Set the environment variable `CELERY_CUSTOM_WORKER_POOL` to the name of
  your desired worker pool implementation implementation.
  - **NOTE:** _The value of the environment variable must be formatted in
              the standard Python/Celery format of_ `package:class`
  - ```bash
    % export CELERY_CUSTOM_WORKER_POOL='celery_aio_pool.pool:AsyncIOPool'
    ```

- Tell Celery to use your desired pool by specifying `--pool=custom` when running your worker instance(s)
  - ```bash
    % celery worker --pool=custom --loglevel=INFO --logfile="$(pwd)/worker.log"
    ```

To verify the pool implementation, examine the output of the `celery inspect stats`
command:

```bash
% celery --app=your_celery_project inspect stats
->  celery@freenas: OK
    {
        ...
        "pool": {
           ...
            "implementation": "celery_aio_pool.pool:AsyncIOPool",
    ...
```


## Developing / Testing / Contributing

> **NOTE:** _Our preferred packaging and dependency manager is [Poetry](https://python-poetry.org/)._
>           _Installation instructions can be found [here](https://python-poetry.org/docs/#installing-with-the-official-installer)._

### Developing

Clone the repo and install the dependencies
```bash
$ git clone https://github.com/the-wondersmith/celery-aio-pool.git \
  && cd celery-aio-pool \
  && poetry install --sync
```

Optionally, if you do not have or prefer _not_ to use Poetry, `celery-aio-pool` is
fully PEP-517 compliant and can be installed directly by any PEP-517-compliant package
manager.

```bash
$ cd celery-aio-pool \
  && pip install -e "$(pwd)"
```

> **TODO:** _Coming Soon™_

### Testing

To run the test suite:

```bash
$ poetry run pytest tests/
```

### Contributing

> **TODO:** _Coming Soon™_
