from . import logger as logging

logger = logging.getLogger(__name__)


def shell(args, **kwargs):
    """
    Replacement for subprocess.run on platforms without python3.5
    :param args: Command and parameters in a list
    :return: A tuple with (command output, return code)
    """
    import subprocess

    output, returncode = '', 0
    logger.debug('running %s', ' '.join(args))
    try:
        if 'cwd' in kwargs:
            kwargs['cwd'] = str(kwargs['cwd'])
        output = subprocess.check_output(
            args, stderr=subprocess.STDOUT, **kwargs)
    except subprocess.CalledProcessError as e:
        returncode = e.returncode
        output = e.output

    return output.decode('utf-8'), returncode


def install_packages(packages):
    args = 'apt-get -y --no-install-recommends install'.split(' ') + \
           list(packages)
    returncode = shell(args)[1]

    if returncode:
        logger.critical('failed to install dependencies ☹. did you add the '
                        'host architecture with dpkg --add-architecture ?')
    return returncode


def build_package(cwd):
    args = ['dpkg-buildpackage', '-us', '-uc']
    arch = parse_debian_control(cwd)['Architecture']
    if arch != 'all':
        args += ['--host-arch', arch]

    output, returncode = shell(args, cwd=cwd)
    logger.debug(output)
    if returncode:
        logger.error('failed to build package ☹')

    return returncode


def build_packages(paths, threads=4):
    from threading import Thread, Event
    from time import sleep

    paths = paths.copy()
    workers = []
    for i in range(threads):
        event = Event()
        event.set()
        workers.append(dict(done=event, path=None))

    def build(done, path):
        logger.info('building %s', path)
        build_package(path)
        done.set()

    while False in [w['done'].is_set() for w in workers] or paths:
        for w in workers:
            if w['done'].is_set() and paths:
                w['done'].clear()
                w['path'] = paths.pop()
                Thread(target=build, kwargs=w).start()
        sleep(1)


def parse_debian_control(cwd):
    """
    Extract some fields from debian/control
    :param cwd: Path to debian source package
    :return: Dict object with fields as keys
    """
    from pathlib import Path
    import re

    field_re = re.compile(r'^([\w-]+)\s*:\s*(.+)')

    content = (Path(cwd) / 'debian' / 'control').read_text()
    control = {}
    for line in content.split('\n'):
        m = field_re.search(line)
        if m:
            g = m.groups()
            control[g[0]] = g[1]

    for k in ('Build-Depends', 'Depends'):
        m = re.findall(r'([^=\s,()]+)\s?(?:\([^)]+\))?', control[k])
        control[k] = m

    return control


def patch_pathlib():
    def path_read_text(self):
        with self.open('r') as f:
            return f.read()

    from pathlib import Path
    if not hasattr(Path, 'read_text'):
        Path.read_text = path_read_text
