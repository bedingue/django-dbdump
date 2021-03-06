"""
Command to do a database dump using database's native tools.

Originally inspired by http://djangosnippets.org/snippets/823/
"""

import os, popen2, time
from optparse import make_option

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

class Command(BaseCommand):
    help = 'Dump database into a file. Only MySQL and PostgreSQL engines are supported.'

    option_list = BaseCommand.option_list + (
        make_option('--destination', dest='backup_directory', default='backups', help='Destination (path) where to place database dump file.'),
        make_option('--filename', dest='filename',  default=False, help='Name of the file'),
        make_option('--db-name', dest='database_name', default='default', help='Name of database (as defined in settings.DATABASES[]) to dump.'),
        make_option('--compress', dest='compression_command', help='Optional command to run (e.g., gzip) to compress output file.'),
        make_option('--quiet', dest='quiet', action='store_true', default=False, help='Be silent.'),
        make_option('--debug', dest='debug', action='store_true', default=False, help='Show commands that are being executed.'),
    )

    def handle(self, *args, **options):
        self.db_name = options.get('database_name', 'default')
        self.compress = options.get('compression_command')
        self.quiet = options.get('quiet')
        self.debug = options.get('debug')

        if self.db_name not in settings.DATABASES:
            raise CommandError('Database %s is not defined in settings.DATABASES' % self.db_name)

        self.engine = settings.DATABASES[self.db_name].get('ENGINE')
        self.db = settings.DATABASES[self.db_name].get('NAME')
        self.user = settings.DATABASES[self.db_name].get('USER')
        self.password = settings.DATABASES[self.db_name].get('PASSWORD')
        self.host = settings.DATABASES[self.db_name].get('HOST')
        self.port = settings.DATABASES[self.db_name].get('PORT')
        self.excluded_tables = settings.DATABASES[self.db_name].get('DB_DUMP_EXCLUDED_TABLES', [])
        self.empty_tables = settings.DATABASES[self.db_name].get('DB_DUMP_EMPTY_TABLES', [])

        backup_directory = options['backup_directory']
        filename = options['filename']

        if not os.path.exists(backup_directory):
            os.makedirs(backup_directory)

        if not filename:
            outfile = self.destination_filename(backup_directory, self.db)
        else:
            outfile = os.path.join(backup_directory, filename)

        if 'mysql' in self.engine:
            self.do_mysql_backup(outfile)
        elif 'postgresql' in self.engine:
            self.do_postgresql_backup(outfile)
        else:
            raise CommandError('Backups of %s engine are not implemented.' % self.engine)

        if self.compress:
            self.run_command('%s %s' % (self.compress, outfile))

    def destination_filename(self, backup_directory, database_name):
        return os.path.join(backup_directory, '%s_backup_%s.sql' % (database_name, time.strftime('%Y%m%d-%H%M%S')))

    def do_mysql_backup(self, outfile):
        if not self.quiet:
            print 'Doing MySQL backup of database "%s" into %s' % (self.db, outfile)

        main_args = []
        if self.user:
            main_args += ['--user=%s' % self.user]
        if self.password:
            main_args += ['--password=%s' % self.password]
        if self.host:
            main_args += ['--host=%s' % self.host]
        if self.port:
            main_args += ['--port=%s' % self.port]

        excluded_args = main_args[:]
        if self.excluded_tables or self.empty_tables:
            excluded_args += ['--ignore-table=%s.%s' % (self.db, excluded_table) for excluded_table in self.excluded_tables + self.empty_tables]

        self.run_command('mysqldump %s > %s' % (' '.join(excluded_args + [self.db]), outfile))

        if self.empty_tables:
            no_data_args = main_args[:] + ['--no-data', self.db]
            no_data_args += [empty_table for empty_table in self.empty_tables]
            self.run_command('mysqldump %s >> %s' % (' '.join(no_data_args), outfile))

    def run_command(self, command):
        if self.debug:
            print command

        os.system(command)

    def do_postgresql_backup(self, outfile):
        print 'This code is totally untested so it is commented out.'

        return
        
        if not self.quiet:
            print 'Doing PostgreSQL backup of database "%s" into %s' % (self.db, outfile)

        main_args = []
        if self.user:
            main_args += ['--username=%s' % self.user]
        if self.password:
            main_args += ['--password']
        if self.host:
            main_args += ['--host=%s' % self.host]
        if self.port:
            main_args += ['--port=%s' % self.port]
 
        excluded_args = main_args[:]
        if self.excluded_tables or self.empty_tables:
            excluded_args += ['--exclude-table=%s' % excluded_table for excluded_table in self.excluded_tables + self.empty_tables]

        self.run_postgresql_command('pg_dump %s > %s' % (' '.join(excluded_args), outfile))

        if self.empty_tables:
            no_data_args = main_args[:] + ['--schema-only']
            no_data_args += ['--table=%s' % empty_table for empty_table in self.empty_tables]
            no_data_args += [self.db]
            self.run_postgresql_command('pg_dump %s > %s' % (' '.join(no_data_args), outfile))

    def run_postgresql_command(self, command):
        if self.debug:
            print command

        pipe = popen2.Popen4(command)

        if self.password:
            pipe.tochild.write('%s\n' % self.password)
            pipe.tochild.close()