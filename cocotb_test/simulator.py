import subprocess
import os
import sys

if sys.version_info.major >= 3:
    from tkinter import _stringify as as_tcl_value
else:
    from Tkinter import _stringify as as_tcl_value


class Simulator(object):
    def __init__(
        self,
        run_dir,
        sim_dir,
        lib_dir,
        lib_ext,
        toplevel,
        toplevel_lang="verilog",
        verilog_sources=[],
        vhdl_sources=[],
        includes=[],
        defines=[],
        extra_compile_args=[],
        extra_simulation_args=[],
        **kwargs
    ):

        self.run_dir = run_dir
        self.sim_dir = sim_dir
        self.lib_dir = lib_dir
        self.lib_ext = lib_ext

        self.toplevel = toplevel
        self.toplevel_lang = toplevel_lang
        self.verilog_sources = self.get_abs_paths(verilog_sources)
        self.vhdl_sources = self.get_abs_paths(vhdl_sources)
        self.includes = self.get_abs_paths(includes)

        self.defines = defines
        self.extra_compile_args = extra_compile_args
        self.extra_simulation_args = extra_simulation_args

        for arg in kwargs:
            setattr(self, arg, kwargs[arg])

        self.sim_file = os.path.join(self.sim_dir, "sim.vvp")

    def build_command(self):
        pass

    def run(self):
        cmds = self.build_command()
        self.execute(cmds)

    def get_include_commands(self, includes):
        pass

    def get_define_commands(self, defines):
        pass

    def get_abs_paths(self, paths):
        paths_abs = []
        for path in paths:
            if os.path.isabs(path):
                paths_abs.append(path)
            else:
                paths_abs.append(os.path.abspath(os.path.join(self.run_dir, path)))

        return paths_abs

    def execute(self, cmds):
        for cmd in cmds:
            print(" ".join(cmd))
            process = subprocess.check_call(cmd, cwd=self.sim_dir)


class Icarus(Simulator):
    def __init__(self, *argv, **kwargs):
        super(Icarus, self).__init__(*argv, **kwargs)

        if self.vhdl_sources:
            raise ValueError("This simulator does not support VHDL")

    def get_include_commands(self, includes):
        include_cmd = []
        for dir in includes:
            include_cmd.append("-I")
            include_cmd.append(dir)

        return include_cmd

    def get_define_commands(self, defines):
        defines_cmd = []
        for define in defines:
            defines_cmd.append("-D")
            defines_cmd.append(define)

        return defines_cmd

    def compile_command(self):

        cmd_compile = (
            [
                "iverilog",
                "-o",
                self.sim_file,
                "-D",
                "COCOTB_SIM=1",
                "-s",
                self.toplevel,
                "-g2012",
            ]
            + self.get_define_commands(self.defines)
            + self.get_include_commands(self.includes)
            + self.extra_compile_args
            + self.verilog_sources
        )

        return cmd_compile

    def run_command(self):
        return (
            ["vvp", "-M", self.lib_dir, "-m", "gpivpi"]
            + self.extra_simulation_args
            + [self.sim_file]
        )

    def build_command(self):
        return [self.compile_command(), self.run_command()]


class Questa(Simulator):
    def get_include_commands(self, includes):
        include_cmd = []
        for dir in includes:
            include_cmd.append("+incdir+" + dir)

        return include_cmd

    def get_define_commands(self, defines):
        defines_cmd = []
        for define in defines:
            defines_cmd.append("+define+" + define)

        return defines_cmd

    def build_script(self):

        do_script = """# Autogenerated file
        onerror {
            quit -f -code 1
        }
        """

        if self.vhdl_sources:
            do_script += "vcom -mixedsvvh +define+COCOTB_SIM {DEFINES} {INCDIR} {EXTRA_ARGS} {VHDL_SOURCES}\n".format(
                VHDL_SOURCES=" ".join(as_tcl_value(v) for v in self.vhdl_sources),
                DEFINES=" ".join(
                    as_tcl_value(v) for v in self.get_define_commands(self.defines)
                ),
                INCDIR=" ".join(
                    as_tcl_value(v) for v in self.get_include_commands(self.includes)
                ),
                EXTRA_ARGS=" ".join(as_tcl_value(v) for v in self.extra_compile_args),
            )
            os.environ["GPI_EXTRA"] = "fli"

        if self.verilog_sources:
            do_script += "vlog -mixedsvvh +define+COCOTB_SIM -sv {DEFINES} {INCDIR} {EXTRA_ARGS} {VERILOG_SOURCES}\n".format(
                VERILOG_SOURCES=" ".join(as_tcl_value(v) for v in self.verilog_sources),
                DEFINES=" ".join(
                    as_tcl_value(v) for v in self.get_define_commands(self.defines)
                ),
                INCDIR=" ".join(
                    as_tcl_value(v) for v in self.get_include_commands(self.includes)
                ),
                EXTRA_ARGS=" ".join(as_tcl_value(v) for v in self.extra_compile_args),
            )

        if self.toplevel_lang == "vhdl":
            do_script += "vsim -onfinish exit -foreign {EXT_NAME} {EXTRA_ARGS} {TOPLEVEL}\n".format(
                TOPLEVEL=as_tcl_value(self.toplevel),
                EXT_NAME=as_tcl_value(
                    "cocotb_init {}".format(
                        os.path.join(self.lib_dir, "libfli." + self.lib_ext)
                    )
                ),
                EXTRA_ARGS=" ".join(
                    as_tcl_value(v) for v in self.extra_simulation_args
                ),
            )
        else:
            do_script += "vsim -onfinish exit -pli {EXT_NAME} {EXTRA_ARGS} {TOPLEVEL}\n".format(
                TOPLEVEL=as_tcl_value(self.toplevel),
                EXT_NAME=as_tcl_value(
                    os.path.join(self.lib_dir, "libvpi." + self.lib_ext)
                ),
                EXTRA_ARGS=" ".join(
                    as_tcl_value(v) for v in self.extra_simulation_args
                ),
            )

        do_script += """log -recursive /*
        onbreak resume
        run -all
        quit
        """

        do_file_path = os.path.join(self.sim_dir, "runsim.do")
        with open(do_file_path, "w") as do_file:
            do_file.write(do_script)

        return do_file_path

    def build_command(self):

        cmd = ["vsim", "-c", "-do", self.build_script()]
        return [cmd]


class Ius(Simulator):
    def __init__(self, *argv, **kwargs):
        super(Ius, self).__init__(*argv, **kwargs)

        os.environ["GPI_EXTRA"] = "vhpi"

    def get_include_commands(self, includes):
        include_cmd = []
        for dir in includes:
            include_cmd.append("-incdir")
            include_cmd.append(dir)

        return include_cmd

    def get_define_commands(self, defines):
        defines_cmd = []
        for define in defines:
            defines_cmd.append("-define")
            defines_cmd.append(define)

        return defines_cmd

    def build_command(self):
        cmd = (
            [
                "irun",
                "-64",
                "-define",
                "COCOTB_SIM=1",
                "-loadvpi",
                os.path.join(self.lib_dir, "libvpi." + self.lib_ext)
                + ":vlog_startup_routines_bootstrap",
                "-plinowarn",
                "-access",
                "+rwc",
                "-top",
                self.toplevel,
            ]
            + self.get_define_commands(self.defines)
            + self.get_include_commands(self.includes)
            + self.extra_compile_args
            + self.extra_simulation_args
            + self.verilog_sources
            + self.vhdl_sources
        )

        return [cmd]


class Vcs(Simulator):
    def get_include_commands(self, includes):
        include_cmd = []
        for dir in includes:
            include_cmd.append("+incdir+" + dir)

        return include_cmd

    def get_define_commands(self, defines):
        defines_cmd = []
        for define in defines:
            defines_cmd.append("+define+" + define)

        return defines_cmd

    def build_command(self):

        pli_cmd = "acc+=rw,wn:*"

        do_file_path = os.path.join(self.sim_dir, "pli.tab")
        with open(do_file_path, "w") as pli_file:
            pli_file.write(pli_cmd)

        cmd_build = (
            [
                "vcs",
                "-full64",
                "-debug",
                "+vpi",
                "-P",
                "pli.tab",
                "-sverilog",
                "+define+COCOTB_SIM=1",
                "-load",
                os.path.join(self.lib_dir, "libvpi." + self.lib_ext),
            ]
            + self.get_define_commands(self.defines)
            + self.get_include_commands(self.includes)
            + self.extra_compile_args
            + self.verilog_sources
        )

        cmd_run = [
            os.path.join(self.sim_dir, "simv"),
            "+define+COCOTB_SIM=1",
        ] + self.extra_simulation_args

        return [cmd_build, cmd_run]


class Ghdl(Simulator):
    def get_include_commands(self, includes):
        include_cmd = []
        for dir in includes:
            include_cmd.append("-I")
            include_cmd.append(dir)

        return include_cmd

    def get_define_commands(self, defines):
        defines_cmd = []
        for define in defines:
            defines_cmd.append("-D")
            defines_cmd.append(define)

    def build_command(self):

        cmd_analyze = []
        for source_file in self.vhdl_sources:
            cmd_analyze.append(["ghdl"] + self.extra_compile_args + ["-a", source_file])

        cmd_elaborate = ["ghdl"] + self.extra_compile_args + ["-e", self.toplevel]

        cmd_run = [
            "ghdl",
            "-r",
            self.toplevel,
            "--vpi=" + os.path.join(self.lib_dir, "libvpi." + self.lib_ext),
        ] + self.extra_simulation_args

        cmd = cmd_analyze + [cmd_elaborate] + [cmd_run]
        return cmd