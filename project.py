#**
# * Copyright (c) 2020 Weitian Leung
# *
# * This file is part of pywpsrpc.
# *
# * This file is distributed under the MIT License.
# * See the LICENSE file for details.
# *
#*

import sipbuild
import os
import sys
import shutil


class PyWpsRpcProject(sipbuild.Project):
    def __init__(self):
        super().__init__(dunder_init=True)

        self.bindings_factories = [RpcWpsApi, RpcWppApi, RpcEtApi]
        self.sdk_inc_dir = os.path.join(self.root_dir, "include")

        # For Arch Linux
        if os.path.exists("/usr/lib/office6"):
            self.sdk_lib_dir = "/usr/lib/office6"
        else:
            self.sdk_lib_dir = "/opt/kingsoft/wps-office/office6"

    def apply_nonuser_defaults(self, tool):
        if self.builder_factory is None:
            self.builder_factory = RpcApiBuilder

        if self.sip_files_dir is None:
            self.sip_files_dir = "sip"

        # must set sip_module
        if self.sip_module is None:
            self.sip_module = "sip"

        if self.sip_include_dirs is None:
            self.sip_include_dirs = [self.root_dir + "/sip/common"]

        super().apply_nonuser_defaults(tool)

    def get_bindings_dir(self):
        # override the default behavior
        return self.name + "/bindings"

    def get_dunder_init(self):
        return """#**
# * Copyright (c) 2020 Weitian Leung
# *
# * This file is part of pywpsrpc.
# *
# * This file is distributed under the MIT License.
# * See the LICENSE file for details.
# *
#*
"""


class RpcApiBindings(sipbuild.Bindings):

    def get_options(self):
        options = super().get_options()

        options.append(sipbuild.Option("QT", option_type=list))

        return options

    def apply_nonuser_defaults(self, tool):
        if self.sip_file is None:
            self.sip_file = self.name + "/" + self.name + ".sip"

        super().apply_nonuser_defaults(tool)

        self.builder_settings.append("QT = %s" % ' '.join(self.QT))

    def apply_user_defaults(self, tool):
        super().apply_user_defaults(tool)


class RpcWpsApi(RpcApiBindings):

    def __init__(self, project):
        dirs = [project.sdk_inc_dir, project.sdk_inc_dir + "/common"]
        dirs.append(project.sdk_inc_dir + "/wps")
        super().__init__(project,
                         "rpcwpsapi",
                         include_dirs=dirs,
                         libraries=["rpcwpsapi_sysqt5"],
                         library_dirs=[project.sdk_lib_dir],
                         QT=["core"])


class RpcWppApi(RpcApiBindings):

    def __init__(self, project):
        dirs = [project.sdk_inc_dir, project.sdk_inc_dir + "/common"]
        dirs.append(project.sdk_inc_dir + "/wpp")
        super().__init__(project,
                         "rpcwppapi",
                         include_dirs=dirs,
                         libraries=["rpcwppapi_sysqt5"],
                         library_dirs=[project.sdk_lib_dir])


class RpcEtApi(RpcApiBindings):

    def __init__(self, project):
        dirs = [project.sdk_inc_dir, project.sdk_inc_dir + "/common"]
        dirs.append(project.sdk_inc_dir + "/et")
        super().__init__(project,
                         "rpcetapi",
                         include_dirs=dirs,
                         libraries=["rpcetapi_sysqt5"],
                         library_dirs=[project.sdk_lib_dir])


# seems that we have no easy way to change the cxx flags
# we need to set the RPATH flags at least
class RpcApiBuilder(sipbuild.Builder):
    def __init__(self, project, **kwargs):
        super().__init__(project, **kwargs)

    def get_options(self):
        options = super().get_options()

        options.append(
            sipbuild.Option("qmake",
                            metavar="<FILE>",
                            help="Specify the qmake executable"))

        return options

    def apply_user_defaults(self, tool):
        if tool in sipbuild.Option.BUILD_TOOLS:
            if self.qmake is None:
                self.qmake = shutil.which("qmake-qt5")
                if not self.qmake:
                    self.qmake = shutil.which("qmake")

            if not self.qmake:
                raise sipbuild.UserException(
                    "Please specify a valid qmake executable")

        super().apply_user_defaults(tool)

    def build_executable(self, buildable, *, fatal=True):
        raise sipbuild.UserException("RpcApiBuilder cannot build executables")

    def build_project(self, target_dir, *, wheel_tag=None):
        installed = []
        sub_dirs = []

        for buildable in self.project.buildables:
            if isinstance(buildable, sipbuild.BuildableModule):
                self._gen_module_pro_file(buildable, target_dir, installed)
            elif type(buildable) is sipbuild.Buildable:
                for installable in buildable.installables:
                    installable.install(
                        target_dir, installed, do_install=False)
            else:
                raise sipbuild.UserException(
                    "RpcApiBuilder cannot build '{0}' buildables".format(type(buildable).__name__))

            sub_dirs.append(buildable.name)

        self.project.progress("Generating the top-level project")

        with open(self.project.build_dir + "/" + self.project.name + ".pro", "w+") as f:
            f.write("TEMPLATE = subdirs\n")
            f.write("CONFIG += ordered\n\n")
            f.write("SUBDIRS = %s\n\n" % ' '.join(sub_dirs))

            for installable in self.project.installables:
                self._install(f, installable, target_dir, installed)

            # install the non-target files
            common_subdir = os.path.join(
                self.project.get_bindings_dir(), "common")
            sip_common = sipbuild.Installable(
                "sip_common", target_subdir=common_subdir)
            common_dir = os.path.join(self.project.root_dir, "sip", "common")
            sip_common_files = [(common_dir + "/" + f)
                                for f in os.listdir(common_dir) if f.endswith(".sip")]
            sip_common.files.extend(sip_common_files)

            self._install(f, sip_common, target_dir, installed)

            # for distinfo
            inventory_file = self.project.build_dir + "/inventory.txt"
            with open(inventory_file, "w+") as inventory:
                inventory.write('\n'.join(installed))
                inventory.write('\n')

            distinfo = ["sip-distinfo",
                        "--project-root", self.project.root_dir,
                        "--generator", os.path.basename(sys.argv[0]),
                        "--prefix", '\\"$(INSTALL_ROOT)\\"',
                        "--inventory", inventory_file]

            if wheel_tag:
                distinfo.append("--wheel-tag")
                distinfo.append(wheel_tag)

            distinfo.append(self.project.get_distinfo_dir(target_dir))

            f.write("distinfo.extra = %s\n" % ' '.join(distinfo))
            f.write("distinfo.path = %s\n" % target_dir)
            f.write("INSTALLS += distinfo\n")

        old_dir = os.getcwd()
        os.chdir(self.project.build_dir)
        self.project.run_command(
            [self.qmake, "-recursive", self.project.name + ".pro"], fatal=True)

        self.project.progress("Compiling the project")
        self._run_make()
        os.chdir(old_dir)

    def install_project(self, target_dir, *, wheel_tag=None):
        self.project.progress("Installing the project")
        old_dir = os.getcwd()
        os.chdir(self.project.build_dir)
        self._run_make(True)
        os.chdir(old_dir)

    def _gen_module_pro_file(self, buildable, target_dir, installed):
        self.project.progress("Generating the %s project" % buildable.target)

        with open(buildable.build_dir + "/" + buildable.target + ".pro", "w+") as f:
            f.write("TEMPLATE = lib\n")
            f.write("CONFIG += plugin no_plugin_name_prefix warn_on\n")
            f.write("CONFIG += %s\n" % ("debug" if buildable.debug else "release"))
            f.write("%s\n" % ' '.join(buildable.builder_settings))
            f.write("TARGET = %s\n\n" % buildable.target)

            if buildable.define_macros:
                f.write("DEFINES += %s\n" % ' '.join(buildable.define_macros))

            f.write("INCLUDEPATH += .\n")
            for dir in buildable.include_dirs:
                f.write("INCLUDEPATH += %s\n" % dir)
            f.write("INCLUDEPATH += %s\n\n" % self.project.py_include_dir)

            for dir in buildable.library_dirs:
                f.write("LIBS += -L%s\n" % dir)
            for lib in buildable.libraries:
                f.write("LIBS += -l%s\n" % lib)

            f.write('\n')

            # hidden symbols
            with open(buildable.build_dir + "/" + buildable.target + ".exp", "w+") as exp:
                exp.write("{ global: PyInit_%s; local: *; };" % buildable.target)

            f.write("QMAKE_LFLAGS += -Wl,--version-script=%s.exp\n" % buildable.target)
            #f.write("QMAKE_LFLAGS_PLUGIN += -Wl,--no-undefined\n")
            f.write("QMAKE_CXXFLAGS += -Wno-attributes\n")
            f.write("QMAKE_RPATHDIR += $ORIGIN /opt/kingsoft/wps-office/office6\n")
            f.write("QMAKE_RPATHDIR += /usr/lib/office6\n\n")

            # for testing
            rpc_dir = os.path.join(self.project.build_dir, self.project.name)
            os.makedirs(rpc_dir, exist_ok=True)
            f.write("QMAKE_POST_LINK = $(COPY_FILE) $(TARGET) %s\n\n" % rpc_dir)

            f.write("HEADERS = %s\n" % " \\\n\t".join(buildable.headers))
            f.write("SOURCES = %s" % " \\\n\t".join(buildable.sources))
            f.write('\n\n')

            f.write("target.path = %s\n" % (target_dir + "/" + self.project.name))
            f.write("INSTALLS += target\n\n")

            # for dist-info
            target_installable = sipbuild.Installable(
                "target", target_subdir=buildable.get_install_subdir())
            installed.append(
                target_installable.get_full_target_dir(target_dir) +
                "/%s.so" % buildable.target)

            for installable in buildable.installables:
                self._install(f, installable, target_dir, installed)

    def _install(self, f, installable, target_dir, installed):
        installable.install(target_dir, installed, do_install=False)

        f.write("{}.path = {}\n".format(
            installable.name,
            installable.get_full_target_dir(target_dir)))
        f.write("{}.files = {}\n".format(
            installable.name,
            " \\\n\t".join(installable.files)))
        f.write("INSTALLS += %s\n\n" % installable.name)

    def _run_make(self, install=False):
        if install:
            # single thread only
            args = ["make", "install"]
        else:
            args = ["make", "-j%s" % os.cpu_count()]

        self.project.run_command(args, fatal=True)