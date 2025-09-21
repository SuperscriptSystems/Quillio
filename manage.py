from flask.cli import FlaskGroup
from app.configuration import app, db
from flask_migrate import MigrateCommand
import click

cli = FlaskGroup(app)

@cli.command("db")
@click.argument("args", nargs=-1)
def db_command(args):
    """Run flask db commands."""
    from flask_migrate import upgrade, downgrade, migrate, init, stamp
    cmd = args[0] if args else None
    if cmd == "init":
        init()
    elif cmd == "migrate":
        migrate()
    elif cmd == "upgrade":
        upgrade()
    elif cmd == "downgrade":
        downgrade()
    elif cmd == "stamp":
        stamp("head")
    else:
        click.echo("Unknown db command")

if __name__ == "__main__":
    cli()
