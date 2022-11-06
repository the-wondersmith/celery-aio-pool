# Celery AsyncIO Pool

![python](https://img.shields.io/pypi/pyversions/celery-aio-pool.svg)
![version](https://img.shields.io/pypi/v/celery-aio-pool.svg)
![downloads](https://img.shields.io/pypi/dm/celery-aio-pool.svg)
![format](https://img.shields.io/pypi/format/celery-aio-pool.svg)

![Logo](https://repository-images.githubusercontent.com/198568368/35298e00-c1e8-11e9-8bcf-76c57ee28db8)

- Free software: GNU Affero General Public License v3+

## Coming Soon™


## Get started ##

### Install using pip from PyPI.org ###

```
pip install celery-aio-pool
```

### Install and test using poetry ###

We use [poetry](https://python-poetry.org/) for packaging and dependency management,
which you may need to [install](https://python-poetry.org/docs/#installing-with-the-official-installer).
Now you can install the Celery Async IOPool:
```
git clone git@github.com:<username>/celery-aio-pool.git
cd celery-aio-pool
poetry install
```
To run the tests:
```
poetry run pytest tests/
```

### Configure Celery ###

At the time of writing, [Celery](https://github.com/celery/celery) does not have
built-in support for out-of-tree pools like the Celery Async IOPool. There is a
[PR #7880](https://github.com/celery/celery/pull/7880) to add this capability.

Pending the PR being merged, if you apply the patch, you will be able to configure
the pool like this:

- Set the environment variable CELERY_CUSTOM_WORKER_POOL to the name of
    an implementation of :class:celery.concurrency.base.BasePool in the
    standard Celery format of "package:class".

- Select this pool using '--pool custom'.

To verify the pool implementation, examine the output of the `celery inspect stats`
command:
```
$ celery -A ... inspect stats
->  celery@freenas: OK
    {
        ...
        "pool": {
           ...
            "implementation": "celery_aio_pool.pool:AsyncIOPool",
```