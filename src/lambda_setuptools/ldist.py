import errno
import os
import shutil
import zipfile

from distutils import log
from distutils.errors import DistutilsPlatformError, DistutilsInternalError
from setuptools import Command
from subprocess import Popen, PIPE


class LDist(Command):

    description = 'build a AWS Lambda compatible distribution'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        # We must create a distribution to install first
        # This is a short-cut to working with the actual build
        # directory, or to using the 'install' command, which
        # will generally only install a zipped egg
        self.run_command('bdist_wheel')
        self._dist_dir = self.get_finalized_command('bdist_wheel').dist_dir

        # Install the package built by bdist_wheel
        # (or bdist, or bdist_wheel, depending on how the user called setup.py
        self._install_dist_package()

        # Now build the lambda package
        self._build_lambda_package()

    def _build_lambda_package(self):
        dist_name = '{}-lambda-{}.zip'.format(self.distribution.get_name(), self.distribution.get_version())
        dist_path = os.path.join(self._dist_dir, dist_name)
        if os.path.exists(dist_path):
            os.remove(dist_path)
        log.info('creating {}'.format(dist_path))
        with zipfile.ZipFile(dist_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            abs_src = os.path.abspath(self._lambda_build_dir)
            for root, _, files in os.walk(self._lambda_build_dir):
                for filename in files:
                    absname = os.path.abspath(os.path.join(root, filename))
                    arcname = absname[len(abs_src) + 1:]
                    log.debug('zipping {} as {}'.format(os.path.join(root, filename), arcname))
                    zf.write(absname, arcname)

    def _install_dist_package(self):
        # Get the name of the package that we just built
        package_name = self.distribution.get_name()
        # Get the dist directory that bdist_wheel put the package in
        # Create the lambda build dir
        self._lambda_build_dir = os.path.join('build', 'ldist-'+package_name)
        try:
            if os.path.exists(self._lambda_build_dir):
                shutil.rmtree(self._lambda_build_dir)
            log.info('creating {}'.format(self._lambda_build_dir))
            os.makedirs(self._lambda_build_dir)
        except OSError as exc:
            if exc.errno == errno.EEXIST and os.path.isdir(self._lambda_build_dir):
                pass
            else:
                raise DistutilsInternalError('{} already exists and is not a directory'.format(self._lambda_build_dir))
        log.info('installing package {} from {} into {}'.format(package_name,
                                                                self._dist_dir,
                                                                self._lambda_build_dir))
        pip = Popen(['pip', 'install',
                     '-f', self._dist_dir,
                     '-t', self._lambda_build_dir, package_name],
                    stdout=PIPE, stderr=PIPE)
        stdout, stderr = pip.communicate()
        log.debug("pip stdout: {}".format(stdout))
        log.debug("pip stderr: {}".format(stderr))

        if pip.returncode is not 0:
            raise DistutilsPlatformError('pip returned unsuccessfully')
