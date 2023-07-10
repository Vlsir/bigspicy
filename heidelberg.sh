#!/bin/bash

/usr/bin/env python3 ~/src/bigspicy/bigspicy.py \
  --import \
  --verilog ~/src/heidelberg/gg-mpw3-2021-Tiles/BRAM/BRAM.v \
  --spef    ~/src/heidelberg/gg-mpw3-2021-Tiles/BRAM/BRAM.spef \
  --verilog ~/src/heidelberg/gg-mpw3-2021-Tiles/CLB/LUT4AB.v \
  --spef    ~/src/heidelberg/gg-mpw3-2021-Tiles/CLB/LUT4AB.spef \
  --verilog ~/src/heidelberg/gg-mpw3-2021-Tiles/DSP/DSP.v \
  --spef    ~/src/heidelberg/gg-mpw3-2021-Tiles/DSP/DSP.spef \
  --verilog ~/src/heidelberg/gg-mpw3-2021-Tiles/E_CPU_IO_bot/E_CPU_IO_bot.v \
  --spef    ~/src/heidelberg/gg-mpw3-2021-Tiles/E_CPU_IO_bot/E_CPU_IO_bot.spef \
  --verilog ~/src/heidelberg/gg-mpw3-2021-Tiles/E_CPU_IO/E_CPU_IO.v \
  --spef    ~/src/heidelberg/gg-mpw3-2021-Tiles/E_CPU_IO/E_CPU_IO.spef \
  --verilog ~/src/heidelberg/gg-mpw3-2021-Tiles/N_term_DSP/N_term_DSP.v \
  --spef    ~/src/heidelberg/gg-mpw3-2021-Tiles/N_term_DSP/N_term_DSP.spef \
  --verilog ~/src/heidelberg/gg-mpw3-2021-Tiles/N_term_RAM_IO/N_term_RAM_IO.v \
  --spef    ~/src/heidelberg/gg-mpw3-2021-Tiles/N_term_RAM_IO/N_term_RAM_IO.spef \
  --verilog ~/src/heidelberg/gg-mpw3-2021-Tiles/N_term_single2/N_term_single2.v \
  --spef    ~/src/heidelberg/gg-mpw3-2021-Tiles/N_term_single2/N_term_single2.spef \
  --verilog ~/src/heidelberg/gg-mpw3-2021-Tiles/N_term_single/N_term_single.v \
  --spef    ~/src/heidelberg/gg-mpw3-2021-Tiles/N_term_single/N_term_single.spef \
  --verilog ~/src/heidelberg/gg-mpw3-2021-Tiles/RAM_IO/RAM_IO.v \
  --spef    ~/src/heidelberg/gg-mpw3-2021-Tiles/RAM_IO/RAM_IO.spef \
  --verilog ~/src/heidelberg/gg-mpw3-2021-Tiles/RegFile/RegFile.v \
  --spef    ~/src/heidelberg/gg-mpw3-2021-Tiles/RegFile/RegFile.spef \
  --verilog ~/src/heidelberg/gg-mpw3-2021-Tiles/S_term_DSP/S_term_DSP.v \
  --spef    ~/src/heidelberg/gg-mpw3-2021-Tiles/S_term_DSP/S_term_DSP.spef \
  --verilog ~/src/heidelberg/gg-mpw3-2021-Tiles/S_term_RAM_IO/S_term_RAM_IO.v \
  --spef    ~/src/heidelberg/gg-mpw3-2021-Tiles/S_term_RAM_IO/S_term_RAM_IO.spef \
  --verilog ~/src/heidelberg/gg-mpw3-2021-Tiles/S_term_single2/S_term_single2.v \
  --spef    ~/src/heidelberg/gg-mpw3-2021-Tiles/S_term_single2/S_term_single2.spef \
  --verilog ~/src/heidelberg/gg-mpw3-2021-Tiles/S_term_single/S_term_single.v \
  --spef    ~/src/heidelberg/gg-mpw3-2021-Tiles/S_term_single/S_term_single.spef \
  --verilog ~/src/heidelberg/gg-mpw3-2021-Tiles/W_CPU_IO_bot/W_CPU_IO_bot.v \
  --spef    ~/src/heidelberg/gg-mpw3-2021-Tiles/W_CPU_IO_bot/W_CPU_IO_bot.spef \
  --verilog ~/src/heidelberg/gg-mpw3-2021-Tiles/W_CPU_IO/W_CPU_IO.v \
  --spef    ~/src/heidelberg/gg-mpw3-2021-Tiles/W_CPU_IO/W_CPU_IO.spef \
  --verilog ~/src/heidelberg/gg-mpw3-2021-Tiles/W_IO/W_IO.v \
  --spef    ~/src/heidelberg/gg-mpw3-2021-Tiles/W_IO/W_IO.spef \
  --verilog ~/src/heidelberg/eFPGA_9x16_Innovus_MPW2/eFPGA_top.v \
  --spef    ~/src/heidelberg/eFPGA_9x16_Innovus_MPW2/eFPGA_top.spef \
  --top eFPGA_top
#  --save /tmp/eFPGA_top.pb

#
#  --spice_header /home/aryap/src/pdk-root/share/pdk/sky130A/libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice \
