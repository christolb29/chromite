# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Common python commands used by various build scripts."""

import inspect
import os
import re
import signal
import subprocess
import sys

_STDOUT_IS_TTY = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()


class CommandResult(object):
  """An object to store various attributes of a child process."""

  def __init__(self):
    self.cmd = None
    self.error = None
    self.output = None
    self.returncode = None


class RunCommandError(Exception):
  """Error caught in RunCommand() method."""
  pass


def RunCommand(cmd, print_cmd=True, error_ok=False, error_message=None,
               exit_code=False, redirect_stdout=False, redirect_stderr=False,
               cwd=None, input=None, enter_chroot=False, shell=False,
               env=None, ignore_sigint=False):
  """Runs a command.

  Args:
    cmd: cmd to run.  Should be input to subprocess.Popen.
    print_cmd: prints the command before running it.
    error_ok: does not raise an exception on error.
    error_message: prints out this message when an error occurrs.
    exit_code: returns the return code of the shell command.
    redirect_stdout: returns the stdout.
    redirect_stderr: holds stderr output until input is communicated.
    cwd: the working directory to run this cmd.
    input: input to pipe into this command through stdin.
    enter_chroot: this command should be run from within the chroot.  If set,
      cwd must point to the scripts directory.
    shell: If shell is True, the specified command will be executed through
      the shell.
    env: If non-None, this is the environment for the new process.
    ignore_sigint: If True, we'll ignore signal.SIGINT before calling the
      child.  This is the desired behavior if we know our child will handle
      Ctrl-C.  If we don't do this, I think we and the child will both get
      Ctrl-C at the same time, which means we'll forcefully kill the child.

  Returns:
    A CommandResult object.

  Raises:
    Exception:  Raises generic exception on error with optional error_message.
  """
  # Set default for variables.
  stdout = None
  stderr = None
  stdin = None
  cmd_result = CommandResult()

  # Modify defaults based on parameters.
  if redirect_stdout: stdout = subprocess.PIPE
  if redirect_stderr: stderr = subprocess.PIPE
  # TODO(sosa): gpylint complains about redefining built-in 'input'.
  #   Can we rename this variable?
  if input: stdin = subprocess.PIPE
  if isinstance(cmd, basestring):
    if enter_chroot: cmd = './enter_chroot.sh -- ' + cmd
    cmd_str = cmd
  else:
    if enter_chroot: cmd = ['./enter_chroot.sh', '--'] + cmd
    cmd_str = ' '.join(cmd)

  # Print out the command before running.
  if print_cmd:
    Info('RunCommand: %s' % cmd_str)
  cmd_result.cmd = cmd

  try:
    proc = subprocess.Popen(cmd, cwd=cwd, stdin=stdin, stdout=stdout,
                            stderr=stderr, shell=shell, env=env)
    if ignore_sigint:
      old_sigint = signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
      (cmd_result.output, cmd_result.error) = proc.communicate(input)
    finally:
      if ignore_sigint:
        signal.signal(signal.SIGINT, old_sigint)

    if exit_code:
      cmd_result.returncode = proc.returncode

    if not error_ok and proc.returncode:
      msg = ('Command "%s" failed.\n' % cmd_str +
             (error_message or cmd_result.error or cmd_result.output or ''))
      raise RunCommandError(msg)
  # TODO(sosa): is it possible not to use the catch-all Exception here?
  except Exception, e:
    if not error_ok:
      raise
    else:
      Warning(str(e))

  return cmd_result


class Color(object):
  """Conditionally wraps text in ANSI color escape sequences."""
  BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)
  BOLD = -1
  COLOR_START = '\033[1;%dm'
  BOLD_START = '\033[1m'
  RESET = '\033[0m'

  def __init__(self, enabled=True):
    self._enabled = enabled

  def Color(self, color, text):
    """Returns text with conditionally added color escape sequences.

    Args:
      color: Text color -- one of the color constants defined in this class.
      text: The text to color.

    Returns:
      If self._enabled is False, returns the original text. If it's True,
      returns text with color escape sequences based on the value of color.
    """
    if not self._enabled:
      return text
    if color == self.BOLD:
      start = self.BOLD_START
    else:
      start = self.COLOR_START % (color + 30)
    return start + text + self.RESET


def Die(message):
  """Emits a red error message and halts execution.

  Args:
    message: The message to be emitted before exiting.
  """
  print >> sys.stderr, (
      Color(_STDOUT_IS_TTY).Color(Color.RED, '\nERROR: ' + message))
  sys.exit(1)


# pylint: disable-msg=W0622
def Warning(message):
  """Emits a yellow warning message and continues execution.

  Args:
    message: The message to be emitted.
  """
  print >> sys.stderr, (
      Color(_STDOUT_IS_TTY).Color(Color.YELLOW, '\nWARNING: ' + message))


def Info(message):
  """Emits a blue informational message and continues execution.

  Args:
    message: The message to be emitted.
  """
  print >> sys.stderr, (
      Color(_STDOUT_IS_TTY).Color(Color.BLUE, '\nINFO: ' + message))


def ListFiles(base_dir):
  """Recurively list files in a directory.

  Args:
    base_dir: directory to start recursively listing in.

  Returns:
    A list of files relative to the base_dir path or
    An empty list of there are no files in the directories.
  """
  directories = [base_dir]
  files_list = []
  while directories:
    directory = directories.pop()
    for name in os.listdir(directory):
      fullpath = os.path.join(directory, name)
      if os.path.isfile(fullpath):
        files_list.append(fullpath)
      elif os.path.isdir(fullpath):
        directories.append(fullpath)

  return files_list


def IsInsideChroot():
  """Returns True if we are inside chroot."""
  return os.path.exists('/etc/debian_chroot')


def GetSrcRoot():
  """Get absolute path to src/scripts/ directory.

  Assuming test script will always be run from descendent of src/scripts.

  Returns:
    A string, absolute path to src/scripts directory. None if not found.
  """
  src_root = None
  match_str = '/src/scripts/'
  test_script_path = os.path.abspath('.')

  path_list = re.split(match_str, test_script_path)
  if path_list:
    src_root = os.path.join(path_list[0], match_str.strip('/'))
    Info ('src_root = %r' % src_root)
  else:
    Info ('No %r found in %r' % (match_str, test_script_path))

  return src_root


def GetChromeosVersion(str_obj):
  """Helper method to parse output for CHROMEOS_VERSION_STRING.

  Args:
    str_obj: a string, which may contain Chrome OS version info.

  Returns:
    A string, value of CHROMEOS_VERSION_STRING environment variable set by
      chromeos_version.sh. Or None if not found.
  """
  if str_obj is not None:
    match = re.search('CHROMEOS_VERSION_STRING=([0-9_.]+)', str_obj)
    if match and match.group(1):
      Info ('CHROMEOS_VERSION_STRING = %s' % match.group(1))
      return match.group(1)

  Info ('CHROMEOS_VERSION_STRING NOT found')
  return None


def GetOutputImageDir(board, cros_version):
  """Construct absolute path to output image directory.

  Args:
    board: a string.
    cros_version: a string, Chrome OS version.

  Returns:
    a string: absolute path to output directory.
  """
  src_root = GetSrcRoot()
  rel_path = 'build/images/%s' % board
  # ASSUME: --build_attempt always sets to 1
  version_str = '-'.join([cros_version, 'a1'])
  output_dir = os.path.join(os.path.dirname(src_root), rel_path, version_str)
  Info ('output_dir = %s' % output_dir)
  return output_dir


def FindRepoDir(path=None):
  """Returns the nearest higher-level repo dir from the specified path.

  Args:
    path: The path to use. Defaults to cwd.
  """
  if path is None:
    path = os.getcwd()
  path = os.path.abspath(path)
  while path != '/':
    repo_dir = os.path.join(path, '.repo')
    if os.path.isdir(repo_dir):
      return repo_dir
    path = os.path.dirname(path)
  return None


def ReinterpretPathForChroot(path):
  """Returns reinterpreted path from outside the chroot for use inside.

  Args:
    path: The path to reinterpret.  Must be in src tree.
  """
  root_path = os.path.join(FindRepoDir(path), '..')

  path_abs_path = os.path.abspath(path)
  root_abs_path = os.path.abspath(root_path)

  # Strip the repository root from the path and strip first /.
  relative_path = path_abs_path.replace(root_abs_path, '')[1:]

  if relative_path == path_abs_path:
    raise Exception('Error: path is outside your src tree, cannot reinterpret.')

  new_path = os.path.join('/home', os.getenv('USER'), 'trunk', relative_path)
  return new_path


def GetCallerName():
  """Returns the name of the calling module with __main__."""
  top_frame = inspect.stack()[-1][0]
  return os.path.basename(top_frame.f_code.co_filename)


class RunCommandException(Exception):
  """Raised when there is an error in OldRunCommand."""
  pass


def OldRunCommand(cmd, print_cmd=True, error_ok=False, error_message=None,
                  exit_code=False, redirect_stdout=False, redirect_stderr=False,
                  cwd=None, input=None, enter_chroot=False, num_retries=0):
  """Legacy run shell command.

  Arguments:
    cmd: cmd to run.  Should be input to subprocess.POpen.  If a string,
      converted to an array using split().
    print_cmd: prints the command before running it.
    error_ok: does not raise an exception on error.
    error_message: prints out this message when an error occurrs.
    exit_code: returns the return code of the shell command.
    redirect_stdout: returns the stdout.
    redirect_stderr: holds stderr output until input is communicated.
    cwd: the working directory to run this cmd.
    input: input to pipe into this command through stdin.
    enter_chroot: this command should be run from within the chroot.  If set,
      cwd must point to the scripts directory.
    num_retries: the number of retries to perform before dying

  Returns:
    If exit_code is True, returns the return code of the shell command.
    Else returns the output of the shell command.

  Raises:
    Exception:  Raises RunCommandException on error with optional error_message.
  """
  # Set default for variables.
  stdout = None
  stderr = None
  stdin = None
  output = ''

  # Modify defaults based on parameters.
  if redirect_stdout:  stdout = subprocess.PIPE
  if redirect_stderr:  stderr = subprocess.PIPE
  if input:  stdin = subprocess.PIPE
  if enter_chroot:  cmd = ['./enter_chroot.sh', '--'] + cmd

  # Print out the command before running.
  if print_cmd:
    Info('PROGRAM(%s) -> RunCommand: %r in dir %s' %
         (GetCallerName(), cmd, cwd))

  for retry_count in range(num_retries + 1):
    try:
      proc = subprocess.Popen(cmd, cwd=cwd, stdin=stdin,
                              stdout=stdout, stderr=stderr)
      (output, error) = proc.communicate(input)
      if exit_code and retry_count == num_retries:
        return proc.returncode

      if proc.returncode == 0:
        break

      raise RunCommandException('Command "%r" failed.\n' % (cmd) +
                                (error_message or error or output or ''))
    except RunCommandException as e:
      if not error_ok and retry_count == num_retries:
        raise e
      else:
        Warning(str(e))
        if print_cmd:
          Info('PROGRAM(%s) -> RunCommand: retrying %r in dir %s' %
               (GetCallerName(), cmd, cwd))

  return output
