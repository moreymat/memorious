import sys
import click
import logging
from tabulate import tabulate

from memorious import settings
from memorious.core import manager, init_memorious, conn
from memorious.worker import get_worker

log = logging.getLogger(__name__)


@click.group()
@click.option("--debug/--no-debug", default=False, envvar="MEMORIOUS_DEBUG")
@click.option("--cache/--no-cache", default=True, envvar="MEMORIOUS_HTTP_CACHE")
@click.option(
    "--incremental/--non-incremental", default=True, envvar="MEMORIOUS_INCREMENTAL"
)
def cli(debug, cache, incremental):
    """Crawler framework for documents and structured scrapers."""
    settings.HTTP_CACHE = cache
    settings.INCREMENTAL = incremental
    settings.DEBUG = debug
    init_memorious()


def get_crawler(name):
    crawler = manager.get(name)
    if crawler is None:
        msg = "Crawler [%s] not found." % name
        raise click.BadParameter(msg, param=crawler)
    return crawler


@cli.command("run")
@click.argument("crawler")
@click.option("--threads", type=int, default=None)
@click.option("--continue-on-error", is_flag=True, default=False)
@click.option("--flush", is_flag=True, default=False)
@click.option("--flushall", is_flag=True, default=False)
def run(crawler, threads=None, continue_on_error=False, flush=False, flushall=False):
    """Run a specified crawler in synchronous mode."""
    crawler = get_crawler(crawler)
    settings._crawler = crawler
    settings.CONTINUE_ON_ERROR = continue_on_error
    if flush:
        crawler.flush()
    if flushall:
        conn.flushall()
    crawler.run()
    if threads is not None and threads > 1:
        if settings.sls.REDIS_URL is None:
            log.warning(
                "REDIS_URL not set. Can't run in multithreaded mode without Redis. Exiting."
            )
            return
        if settings.DATASTORE_URI.startswith("sqlite:///"):
            log.warning(
                "Can't run in multithreaded mode with sqlite database. Exiting."
            )
            return
    worker = get_worker(num_threads=threads)
    code = worker.run(blocking=False)
    sys.exit(code)


@cli.command()
@click.argument("crawler")
def cancel(crawler):
    """Abort execution of a specified crawler."""
    crawler = get_crawler(crawler)
    crawler.cancel()


@cli.command()
@click.argument("crawler")
def flush(crawler):
    """Delete all data generated by a crawler."""
    crawler = get_crawler(crawler)
    crawler.flush()


@cli.command("flush-tags")
@click.argument("crawler")
def flush_tags(crawler):
    """Delete all tags generated by a crawler."""
    crawler = get_crawler(crawler)
    crawler.flush_tags()


@cli.command("list")
def index():
    """List the available crawlers."""
    crawler_list = []
    for crawler in manager:
        crawler_list.append(
            [
                crawler.name,
                crawler.description,
            ]
        )
    headers = [
        "Name",
        "Description",
    ]
    print(tabulate(crawler_list, headers=headers))


@cli.command("status")
@click.argument("crawler")
def status(crawler):
    """Status of a crawler."""
    crawler = get_crawler(crawler)
    prop_list = []
    last_run = crawler.last_run
    if last_run:
        last_run = last_run.isoformat() + " UTC"
    prop_list.append(
        [
            crawler.name,
            crawler.description,
            crawler.is_running,
            last_run,
            crawler.op_count,
            crawler.pending,
        ]
    )
    headers = [
        "Name",
        "Description",
        "Running?",
        "Last Active",
        "Op Count",
        "Pending Ops",
    ]
    print(tabulate(prop_list, headers=headers))


@cli.command()
def killthekitten():
    """Completely kill redis contents."""
    from memorious.core import connect_redis

    conn = connect_redis()
    conn.flushall()


def main():
    cli(obj={})


if __name__ == "__main__":
    main()
