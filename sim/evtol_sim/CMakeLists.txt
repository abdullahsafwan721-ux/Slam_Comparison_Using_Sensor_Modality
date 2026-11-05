cmake_minimum_required(VERSION 3.10)
project(evtol_sim)

find_package(catkin REQUIRED COMPONENTS roscpp gazebo_ros)
find_package(gazebo REQUIRED)

catkin_package()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${GAZEBO_CXX_FLAGS}")
include_directories(${GAZEBO_INCLUDE_DIRS} ${catkin_INCLUDE_DIRS})
link_directories(${GAZEBO_LIBRARY_DIRS})

# Model plugin: builds to /ws/devel/lib/libtrajectory_driver.so
add_library(trajectory_driver SHARED src/trajectory_driver.cpp)
target_link_libraries(trajectory_driver ${GAZEBO_LIBRARIES})
