# SPDX-FileCopyrightText: 2025-2026 GLITech
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import numpy as np
from typing import Any, Dict

DEFAULT_URDF_XML: str = """\
<?xml version='1.0' encoding='utf-8'?>
<robot name="ghand5-right">
  <link name="base_link">
    <inertial>
      <origin xyz="-0.00050748 0.0016354 0.051276" rpy="0 0 0" />
      <mass value="0.42244" />
      <inertia ixx="0.00026365" ixy="4.5003E-07" ixz="-8.8693E-07" iyy="0.00049058" iyz="-5.3643E-06" izz="0.00026666" />
    </inertial>
    <visual>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/base_link.STL" />
      </geometry>
      <material name="">
        <color rgba="0.79216 0.81961 0.93333 1" />
      </material>
    </visual>
    <collision>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/base_link.STL" />
      </geometry>
    </collision>
  </link>
  <link name="LF_MCP_link">
    <inertial>
      <origin xyz="-0.0148714653082719 0.00503228360598384 3.88988564467389E-05" rpy="0 0 0" />
      <mass value="0.0264433801741145" />
      <inertia ixx="1.12668646393785E-06" ixy="8.37169257084027E-08" ixz="5.91905050514431E-09" iyy="3.74496576715797E-06" iyz="9.87594951906574E-10" izz="3.38720577903523E-06" />
    </inertial>
    <visual>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/LF_MCP_link.STL" />
      </geometry>
      <material name="">
        <color rgba="0.792156862745098 0.819607843137255 0.933333333333333 1" />
      </material>
    </visual>
    <collision>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/LF_MCP_link.STL" />
      </geometry>
    </collision>
  </link>
  <joint name="LF_MCP" type="revolute">
    <origin xyz="-0.034185 0.0010527 0.092671" rpy="0 1.5014 0" />
    <parent link="base_link" />
    <child link="LF_MCP_link" />
    <axis xyz="0 0 1" />
    <limit lower="0" upper="1.5707963267949" effort="0" velocity="0" />
  </joint>
  <link name="LF_PIP_link">
    <inertial>
      <origin xyz="-0.0097068390207721 -0.00148924633551032 3.25008649219756E-05" rpy="0 0 0" />
      <mass value="0.0106101494180424" />
      <inertia ixx="3.90064134324655E-07" ixy="-3.55011645679185E-08" ixz="-1.21708615677339E-09" iyy="7.04951964281311E-07" iyz="-1.1521038821448E-09" izz="4.68172618370353E-07" />
    </inertial>
    <visual>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/LF_PIP_link.STL" />
      </geometry>
      <material name="">
        <color rgba="0.792156862745098 0.819607843137255 0.933333333333333 1" />
      </material>
    </visual>
    <collision>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/LF_PIP_link.STL" />
      </geometry>
    </collision>
  </link>
  <joint name="LF_PIP" type="revolute">
    <origin xyz="-0.035829 0.0069671 0" rpy="0 0 0" />
    <parent link="LF_MCP_link" />
    <child link="LF_PIP_link" />
    <axis xyz="0 0 1" />
    <limit lower="0" upper="1.65806278939461" effort="0" velocity="0" />
  </joint>
  <link name="LF_DIP_link">
    <inertial>
      <origin xyz="-0.0108225975388941 0.00329558485146861 6.71873393934264E-08" rpy="0 0 0" />
      <mass value="0.0178564975749226" />
      <inertia ixx="3.42104582604646E-07" ixy="7.34889433848766E-08" ixz="3.08841112891673E-11" iyy="6.78587150944913E-07" iyz="3.08234175645799E-11" izz="5.82509349683866E-07" />
    </inertial>
    <visual>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/LF_DIP_link.STL" />
      </geometry>
      <material name="">
        <color rgba="0.792156862745098 0.819607843137255 0.933333333333333 1" />
      </material>
    </visual>
    <collision>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/LF_DIP_link.STL" />
      </geometry>
    </collision>
  </link>
  <joint name="LF_DIP" type="revolute">
    <origin xyz="-0.017923 -0.0052616 0" rpy="0 0 0" />
    <parent link="LF_PIP_link" />
    <child link="LF_DIP_link" />
    <axis xyz="0 0 1" />
    <limit lower="0" upper="1.5707963267949" effort="0" velocity="0" />
  </joint>
  <link name="RF_MCP_link">
    <inertial>
      <origin xyz="-0.0200154438846792 0.00499783524834638 1.82089110935431E-05" rpy="0 0 0" />
      <mass value="0.0343124145280853" />
      <inertia ixx="1.44654607301467E-06" ixy="1.50579553732885E-07" ixz="8.03944031790484E-09" iyy="5.95506883420712E-06" iyz="-1.04146567678546E-10" izz="5.5067012402718E-06" />
    </inertial>
    <visual>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/RF_MCP_link.STL" />
      </geometry>
      <material name="">
        <color rgba="0.792156862745098 0.819607843137255 0.933333333333333 1" />
      </material>
    </visual>
    <collision>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/RF_MCP_link.STL" />
      </geometry>
    </collision>
  </link>
  <joint name="RF_MCP" type="revolute">
    <origin xyz="-0.013536 0.0010527 0.096396" rpy="0 1.5343 0" />
    <parent link="base_link" />
    <child link="RF_MCP_link" />
    <axis xyz="0 0 1" />
    <limit lower="0" upper="1.5707963267949" effort="0" velocity="0" />
  </joint>
  <link name="RF_PIP_link">
    <inertial>
      <origin xyz="-0.0129146504315271 -0.00163014139965735 2.91803546564016E-05" rpy="0 0 0" />
      <mass value="0.014440256274874" />
      <inertia ixx="4.79041612065652E-07" ixy="-6.99063128124064E-08" ixz="-4.01061987623134E-09" iyy="1.15969535072989E-06" iyz="-1.27988357446742E-09" izz="9.20906233378606E-07" />
    </inertial>
    <visual>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/RF_PIP_link.STL" />
      </geometry>
      <material name="">
        <color rgba="0.792156862745098 0.819607843137255 0.933333333333333 1" />
      </material>
    </visual>
    <collision>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/RF_PIP_link.STL" />
      </geometry>
    </collision>
  </link>
  <joint name="RF_PIP" type="revolute">
    <origin xyz="-0.044412 0.0070232 0" rpy="0 0 0" />
    <parent link="RF_MCP_link" />
    <child link="RF_PIP_link" />
    <axis xyz="0 0 1" />
    <limit lower="0" upper="1.74532925199433" effort="0" velocity="0" />
  </joint>
  <link name="RF_DIP_link">
    <inertial>
      <origin xyz="-0.010960500689851 0.00395375609705622 -1.36515418905012E-07" rpy="0 0 0" />
      <mass value="0.0185881209622168" />
      <inertia ixx="3.65166569200714E-07" ixy="9.41885748790088E-08" ixz="5.28805306276357E-11" iyy="7.27839723666553E-07" iyz="2.95230916292615E-11" izz="6.40891415778403E-07" />
    </inertial>
    <visual>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/RF_DIP_link.STL" />
      </geometry>
      <material name="">
        <color rgba="0.792156862745098 0.819607843137255 0.933333333333333 1" />
      </material>
    </visual>
    <collision>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/RF_DIP_link.STL" />
      </geometry>
    </collision>
  </link>
  <joint name="RF_DIP" type="revolute">
    <origin xyz="-0.022986 -0.0050638 0" rpy="0 0 0" />
    <parent link="RF_PIP_link" />
    <child link="RF_DIP_link" />
    <axis xyz="0 0 1" />
    <limit lower="0" upper="1.5707963267949" effort="0" velocity="0" />
  </joint>
  <link name="MF_MCP_link">
    <inertial>
      <origin xyz="-0.020015657132935 0.00499700098081666 1.82312477741663E-05" rpy="0 0 0" />
      <mass value="0.0343123953862461" />
      <inertia ixx="1.44653388682065E-06" ixy="1.50396098280116E-07" ixz="8.02999366825671E-09" iyy="5.95507602098445E-06" iyz="-1.04754350214213E-10" izz="5.50669556045967E-06" />
    </inertial>
    <visual>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/MF_MCP_link.STL" />
      </geometry>
      <material name="">
        <color rgba="0.792156862745098 0.819607843137255 0.933333333333333 1" />
      </material>
    </visual>
    <collision>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/MF_MCP_link.STL" />
      </geometry>
    </collision>
  </link>
  <joint name="MF_MCP" type="revolute">
    <origin xyz="0.007228 0.0010527 0.099132" rpy="-1.5709 1.5708 -1.5709" />
    <parent link="base_link" />
    <child link="MF_MCP_link" />
    <axis xyz="0 0 1" />
    <limit lower="0" upper="1.5707963267949" effort="0" velocity="0" />
  </joint>
  <link name="MF_PIP_link">
    <inertial>
      <origin xyz="-0.0129145853484956 -0.00163067562965549 2.9179567707819E-05" rpy="0 0 0" />
      <mass value="0.014440252492985" />
      <inertia ixx="4.79047400046214E-07" ixy="-6.9934513312764E-08" ixz="-4.01051759793927E-09" iyy="1.15968950499497E-06" iyz="-1.2799849290505E-09" izz="9.20906207415852E-07" />
    </inertial>
    <visual>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/MF_PIP_link.STL" />
      </geometry>
      <material name="">
        <color rgba="0.792156862745098 0.819607843137255 0.933333333333333 1" />
      </material>
    </visual>
    <collision>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/MF_PIP_link.STL" />
      </geometry>
    </collision>
  </link>
  <joint name="MF_PIP" type="revolute">
    <origin xyz="-0.044413 0.0070214 0" rpy="0 0 0" />
    <parent link="MF_MCP_link" />
    <child link="MF_PIP_link" />
    <axis xyz="0 0 1" />
    <limit lower="0" upper="1.74532925199433" effort="0" velocity="0" />
  </joint>
  <link name="MF_DIP_link">
    <inertial>
      <origin xyz="-0.0109606311312518 0.00395332931435218 -1.59377583372131E-07" rpy="0 0 0" />
      <mass value="0.0185881308582604" />
      <inertia ixx="3.65159369510818E-07" ixy="9.41727717913628E-08" ixz="4.86556542668534E-11" iyy="7.27847573227014E-07" iyz="2.86792910011E-11" izz="6.40890831314597E-07" />
    </inertial>
    <visual>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/MF_DIP_link.STL" />
      </geometry>
      <material name="">
        <color rgba="0.792156862745098 0.819607843137255 0.933333333333333 1" />
      </material>
    </visual>
    <collision>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/MF_DIP_link.STL" />
      </geometry>
    </collision>
  </link>
  <joint name="MF_DIP" type="revolute">
    <origin xyz="-0.022986 -0.0050648 0" rpy="0 0 0" />
    <parent link="MF_PIP_link" />
    <child link="MF_DIP_link" />
    <axis xyz="0 0 1" />
    <limit lower="0" upper="1.5707963267949" effort="0" velocity="0" />
  </joint>
  <link name="FF_MCP_AA_link">
    <inertial>
      <origin xyz="-1.61713798380037E-07 -0.000374611814496814 0.00649307088361358" rpy="0 0 0" />
      <mass value="0.00258839121321602" />
      <inertia ixx="3.84640517480584E-08" ixy="-8.47527178940796E-13" ixz="-1.6550795182512E-12" iyy="5.98301094836961E-08" iyz="-2.67449990938072E-09" izz="3.65467948056483E-08" />
    </inertial>
    <visual>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/FF_MCP_AA_link.STL" />
      </geometry>
      <material name="">
        <color rgba="0.792156862745098 0.819607843137255 0.933333333333333 1" />
      </material>
    </visual>
    <collision>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/FF_MCP_AA_link.STL" />
      </geometry>
    </collision>
  </link>
  <joint name="FF_MCP_AA" type="revolute">
    <origin xyz="0.028566 0.013553 0.095927" rpy="1.5708 0 0" />
    <parent link="base_link" />
    <child link="FF_MCP_AA_link" />
    <axis xyz="0 0 -1" />
    <limit lower="-0.174532925199433" upper="0.174532925199433" effort="0" velocity="0" />
  </joint>
  <link name="FF_MCP_link">
    <inertial>
      <origin xyz="-0.0203264267049536 0.00517149606041659 1.4901911354611E-05" rpy="0 0 0" />
      <mass value="0.0388429620559521" />
      <inertia ixx="1.71064556799332E-06" ixy="2.84855769896218E-07" ixz="9.34579493350336E-09" iyy="6.34003203740085E-06" iyz="-8.30355564685866E-10" izz="5.91606496421187E-06" />
    </inertial>
    <visual>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/FF_MCP_link.STL" />
      </geometry>
      <material name="">
        <color rgba="0.792156862745098 0.819607843137255 0.933333333333333 1" />
      </material>
    </visual>
    <collision>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/FF_MCP_link.STL" />
      </geometry>
    </collision>
  </link>
  <joint name="FF_MCP" type="revolute">
    <origin xyz="0 0 0.0125" rpy="-1.5708 0 -1.5708" />
    <parent link="FF_MCP_AA_link" />
    <child link="FF_MCP_link" />
    <axis xyz="0 0 1" />
    <limit lower="0" upper="1.5707963267949" effort="0" velocity="0" />
  </joint>
  <link name="FF_PIP_link">
    <inertial>
      <origin xyz="-0.0129209246996119 -0.00157965828614821 2.91720492550246E-05" rpy="0 0 0" />
      <mass value="0.0144402684934038" />
      <inertia ixx="4.78507380757098E-07" ixy="-6.72433621795968E-08" ixz="-4.01468010985818E-09" iyy="1.16023213096375E-06" iyz="-1.26496256063458E-09" izz="9.20907889027397E-07" />
    </inertial>
    <visual>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/FF_PIP_link.STL" />
      </geometry>
      <material name="">
        <color rgba="0.792156862745098 0.819607843137255 0.933333333333333 1" />
      </material>
    </visual>
    <collision>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/FF_PIP_link.STL" />
      </geometry>
    </collision>
  </link>
  <joint name="FF_PIP" type="revolute">
    <origin xyz="-0.044403 0.0070773 0" rpy="0 0 0" />
    <parent link="FF_MCP_link" />
    <child link="FF_PIP_link" />
    <axis xyz="0 0 1" />
    <limit lower="0" upper="1.74532925199433" effort="0" velocity="0" />
  </joint>
  <link name="FF_DIP_link">
    <inertial>
      <origin xyz="-0.0109378103100737 0.00401604755829069 -1.48789861452447E-07" rpy="0 0 0" />
      <mass value="0.0185881017119488" />
      <inertia ixx="3.66249322121008E-07" ixy="9.624379757881E-08" ixz="4.8438393434636E-11" iyy="7.26755468132449E-07" iyz="2.86313803287822E-11" izz="6.4089089648744E-07" />
    </inertial>
    <visual>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/FF_DIP_link.STL" />
      </geometry>
      <material name="">
        <color rgba="0.792156862745098 0.819607843137255 0.933333333333333 1" />
      </material>
    </visual>
    <collision>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/FF_DIP_link.STL" />
      </geometry>
    </collision>
  </link>
  <joint name="FF_DIP" type="revolute">
    <origin xyz="-0.023006 -0.0049739 0" rpy="0 0 0" />
    <parent link="FF_PIP_link" />
    <child link="FF_DIP_link" />
    <axis xyz="0 0 1" />
    <limit lower="0" upper="1.5707963267949" effort="0" velocity="0" />
  </joint>
  <link name="Thumb_TMC_PS_link">
    <inertial>
      <origin xyz="-0.00286579384018245 -8.14165588735039E-05 0.00727703884478214" rpy="0 0 0" />
      <mass value="0.050441684617305" />
      <inertia ixx="1.02738403250133E-05" ixy="1.91583245033417E-07" ixz="-1.65644746936581E-07" iyy="5.32993593590205E-06" iyz="1.71933913220007E-07" izz="1.34948360952034E-05" />
    </inertial>
    <visual>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/Thumb_TMC_PS_link.STL" />
      </geometry>
      <material name="">
        <color rgba="0.792156862745098 0.819607843137255 0.933333333333333 1" />
      </material>
    </visual>
    <collision>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/Thumb_TMC_PS_link.STL" />
      </geometry>
    </collision>
  </link>
  <joint name="Thumb_TMC_PS" type="revolute">
    <origin xyz="0.013492 -0.016547 0.0372" rpy="1.5708 0 0" />
    <parent link="base_link" />
    <child link="Thumb_TMC_PS_link" />
    <axis xyz="0 0 1" />
    <limit lower="-0.174532925199433" upper="1.0471975511966" effort="0" velocity="0" />
  </joint>
  <link name="Thumb_TMC_AA_link">
    <inertial>
      <origin xyz="0.000429256557170316 -0.0081985809982227 -0.0018889698513071" rpy="0 0 0" />
      <mass value="0.00783292793179758" />
      <inertia ixx="2.2033705259923E-07" ixy="1.20902185363149E-08" ixz="-1.00206656384408E-09" iyy="1.92376273377408E-07" iyz="2.18153540830078E-08" izz="3.71557184428904E-07" />
    </inertial>
    <visual>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/Thumb_TMC_AA_link.STL" />
      </geometry>
      <material name="">
        <color rgba="0.792156862745098 0.819607843137255 0.933333333333333 1" />
      </material>
    </visual>
    <collision>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/Thumb_TMC_AA_link.STL" />
      </geometry>
    </collision>
  </link>
  <joint name="Thumb_TMC_AA" type="revolute">
    <origin xyz="0.0038094 -0.0075994 0.0089" rpy="-1.5708 1.5708 0" />
    <parent link="Thumb_TMC_PS_link" />
    <child link="Thumb_TMC_AA_link" />
    <axis xyz="0 0 -1" />
    <limit lower="0.349065850398866" upper="1.5707963267949" effort="0" velocity="0" />
  </joint>
  <link name="Thumb_TMC_FE_link">
    <inertial>
      <origin xyz="-0.00349926354871747 0.0193706933165962 -4.15502449385256E-05" rpy="0 0 0" />
      <mass value="0.0655978679831151" />
      <inertia ixx="1.71031458149851E-05" ixy="-2.19720162598876E-07" ixz="9.92897297754065E-09" iyy="6.3721054469053E-06" iyz="8.86297050641261E-08" izz="1.33108986044732E-05" />
    </inertial>
    <visual>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/Thumb_TMC_FE_link.STL" />
      </geometry>
      <material name="">
        <color rgba="0.792156862745098 0.819607843137255 0.933333333333333 1" />
      </material>
    </visual>
    <collision>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/Thumb_TMC_FE_link.STL" />
      </geometry>
    </collision>
  </link>
  <joint name="Thumb_TMC_FE" type="revolute">
    <origin xyz="0 -0.016971 -0.0001353" rpy="1.5708 -1.1112 1.5708" />
    <parent link="Thumb_TMC_AA_link" />
    <child link="Thumb_TMC_FE_link" />
    <axis xyz="0 0 -1" />
    <limit lower="0" upper="0.872664625997165" effort="0" velocity="0" />
  </joint>
  <link name="Thumb_MCP_link">
    <inertial>
      <origin xyz="-0.00189957206408813 -0.0193191656464625 -1.5485936652359E-05" rpy="0 0 0" />
      <mass value="0.0211695183057074" />
      <inertia ixx="2.97455165240941E-06" ixy="-4.15655138904627E-07" ixz="1.13484006210276E-09" iyy="1.34602789019338E-06" iyz="2.74124533184906E-09" izz="2.72195996652612E-06" />
    </inertial>
    <visual>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/Thumb_MCP_link.STL" />
      </geometry>
      <material name="">
        <color rgba="0.792156862745098 0.819607843137255 0.933333333333333 1" />
      </material>
    </visual>
    <collision>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/Thumb_MCP_link.STL" />
      </geometry>
    </collision>
  </link>
  <joint name="Thumb_MCP" type="revolute">
    <origin xyz="-0.0067 0.0415 0" rpy="0 0 -3.1416" />
    <parent link="Thumb_TMC_FE_link" />
    <child link="Thumb_MCP_link" />
    <axis xyz="0 0 -1" />
    <limit lower="0" upper="1.15191730631626" effort="0" velocity="0" />
  </joint>
  <link name="Thumb_IP_link">
    <inertial>
      <origin xyz="-0.00225412538400287 -0.010722713724769 -4.31535807393843E-05" rpy="0 0 0" />
      <mass value="0.0339937040774307" />
      <inertia ixx="1.88201119626116E-06" ixy="-2.70429587154286E-07" ixz="-2.16738339704917E-09" iyy="1.03311847359096E-06" iyz="-2.53444185990485E-09" izz="1.61436170150998E-06" />
    </inertial>
    <visual>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/Thumb_IP_link.STL" />
      </geometry>
      <material name="">
        <color rgba="0.792156862745098 0.819607843137255 0.933333333333333 1" />
      </material>
    </visual>
    <collision>
      <origin xyz="0 0 0" rpy="0 0 0" />
      <geometry>
        <mesh filename="ghand5_system/meshes/hands/visual/right/Thumb_IP_link.STL" />
      </geometry>
    </collision>
  </link>
  <joint name="Thumb_IP" type="revolute">
    <origin xyz="-0.0049669 -0.03505 0" rpy="-3.1416 0 3.1184" />
    <parent link="Thumb_MCP_link" />
    <child link="Thumb_IP_link" />
    <axis xyz="0 0 1" />
    <limit lower="0" upper="1.5707963267949" effort="0" velocity="0" />
  </joint>
</robot>
"""

DEFAULT_CAPSULE_PARAMS: Dict[str, Dict[str, Any]] = {
    "LF_MCP_link": {
        "xyz": np.array([0.0, 0.004, 0.0], dtype=float),
        "radius": 0.01,
        "k": 0.03,
        "theta_prime": 3.141592653589793,
    },
    "LF_PIP_link": {
        "xyz": np.array([0.0, -0.002, 0.0], dtype=float),
        "radius": 0.0078,
        "k": 0.015,
        "theta_prime": 3.141592653589793,
    },
    "LF_DIP_link": {
        "xyz": np.array([0.0, 0.003, 0.0], dtype=float),
        "radius": 0.0076,
        "k": 0.015,
        "theta_prime": 3.141592653589793,
    },
    "RF_MCP_link": {
        "xyz": np.array([-0.003, 0.004, 0.0], dtype=float),
        "radius": 0.0098,
        "k": 0.035,
        "theta_prime": 3.141592653589793,
    },
    "RF_PIP_link": {
        "xyz": np.array([0.0, -0.003, 0.0], dtype=float),
        "radius": 0.0078,
        "k": 0.021,
        "theta_prime": 3.141592653589793,
    },
    "RF_DIP_link": {
        "xyz": np.array([-0.002, 0.0035, 0.0], dtype=float),
        "radius": 0.0075,
        "k": 0.014,
        "theta_prime": 3.141592653589793,
    },
    "MF_MCP_link": {
        "xyz": np.array([-0.004, 0.004, 0.0], dtype=float),
        "radius": 0.009,
        "k": 0.03,
        "theta_prime": 3.141592653589793,
    },
    "MF_PIP_link": {
        "xyz": np.array([0.0, -0.0025, 0.0], dtype=float),
        "radius": 0.0075,
        "k": 0.022,
        "theta_prime": 3.141592653589793,
    },
    "MF_DIP_link": {
        "xyz": np.array([0.0, 0.004, 0.0], dtype=float),
        "radius": 0.0075,
        "k": 0.015,
        "theta_prime": 3.141592653589793,
    },
    "FF_MCP_link": {
        "xyz": np.array([-0.002, 0.004, 0.0], dtype=float),
        "radius": 0.009,
        "k": 0.035,
        "theta_prime": 3.141592653589793,
    },
    "FF_PIP_link": {
        "xyz": np.array([-0.002, -0.0025, 0.0], dtype=float),
        "radius": 0.0075,
        "k": 0.02,
        "theta_prime": 3.141592653589793,
    },
    "FF_DIP_link": {
        "xyz": np.array([-0.002, 0.0035, 0.0], dtype=float),
        "radius": 0.0075,
        "k": 0.015,
        "theta_prime": 3.141592653589793,
    },
    "Thumb_TMC_FE_link": {
        "xyz": np.array([-0.0022, 0.0, 0.0], dtype=float),
        "radius": 0.014,
        "k": 0.03,
        "theta_prime": 1.5707963267948966,
    },
    "Thumb_MCP_link": {
        "xyz": np.array([-0.003, -0.004, 0.0], dtype=float),
        "radius": 0.0095,
        "k": 0.028,
        "theta_prime": 4.71238898038469,
    },
    "Thumb_IP_link": {
        "xyz": np.array([-0.002, 0.0, 0.0], dtype=float),
        "radius": 0.0095,
        "k": 0.016,
        "theta_prime": 4.71238898038469,
    },
}
