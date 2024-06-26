#! /usr/bin/env python

import numpy as np
from pyquaternion import Quaternion
import os
import argparse
import cv2

# ROS libraries
import rosbag
from cv_bridge import CvBridge

def main():
    """Extract a folder of images from a rosbag.
    """ 

    parser = argparse.ArgumentParser(description="Process sequential poses.")
    parser.add_argument("survey", help="Indicate survey number")
    parser.add_argument("date", help="Dataset date.")
    parser.add_argument("robot", help="Which robot")

    args = parser.parse_args()

    bag_dir = f"{args.date}/{args.robot}/bags/survey{args.survey}"

    output_dir = f"{args.date}/{args.robot}/bayer/survey{args.survey}"
    output_dir_poses = f"{args.date}/{args.robot}/pose/survey{args.survey}"
    try: os.mkdir(output_dir)
    except FileExistsError:
        print(f"{output_dir} already exists!")
    try: os.mkdir(output_dir_poses)
    except FileExistsError:
        print(f"{output_dir_poses} already exists!")

    bridge = CvBridge()

    body_to_cam_trans = np.array([0.1157+0.002, -0.0422, -0.0826])

    # if args.robot=="bsharp":
    # # nav_cam_tf = transform(vec3(0.1157+0.002, -0.0422, -0.0826), quat4(-0.46938154, -0.52978318, -0.5317378, -0.46504373))
    #     body_to_cam_quat_xyzw = np.array([-0.46938154, -0.52978318, -0.5317378, -0.46504373])
    # elif args.robot=="queen" or args.robot=="bumble" or args.robot=="sim":
    # # nav_cam_transform = transform(vec3(0.1157+0.002, -0.0422, -0.0826), quat4(0.500, 0.500, 0.500, 0.500) ),
    #     body_to_cam_quat_xyzw = np.array([0.500, 0.500, 0.500, 0.500])
    body_to_cam_quat_xyzw = np.array([0.500, 0.500, 0.500, 0.500])

    body_to_cam_quat_wxyz = Quaternion(w=body_to_cam_quat_xyzw[3],x=body_to_cam_quat_xyzw[0],y=body_to_cam_quat_xyzw[1],z=body_to_cam_quat_xyzw[2])
    body_to_cam_transf = body_to_cam_quat_wxyz.transformation_matrix
    body_to_cam_transf[0:3,3] = body_to_cam_trans.T

    if args.robot=="sim":
        jpm_to_world = np.zeros((4,4))
        # note: rpy in ROS is ZYX Euler angles representation
        # jpm_to_world_rpy = np.array([3.1415, 0, -1.570796])
        jpm_to_world[0:3, 3] = np.array([10.9358938, -2.3364698, 4.8505872])
        jpm_to_world[0:3, 0:3] = np.array([[0,-1,0],[-1,0,0],[0, 0,-1]])
        jpm_to_world[3,3] = 1
        img_topic = '/hw/cam_nav'
    elif args.robot=="bsharp":
        jpm_to_world = np.identity(4)
        img_topic = '/hw/cam_nav_bayer'
    else:
        jpm_to_world = np.zeros((4,4))
        jpm_to_world[0:3, 3] = np.array([10.9358938, -2.3364698, 4.8505872])
        jpm_to_world[0:3, 0:3] = np.array([[0,-1,0],[-1,0,0],[0, 0,-1]])
        jpm_to_world[3,3] = 1
        img_topic = '/hw/cam_nav_bayer'

    bag_number = 0
    bags = sorted(os.listdir(bag_dir))
    print(f"Survey: {args.survey}")

    pose_list = []
    pose_time = []
    image_time = []
    
    for bag_file in bags:

        bag = rosbag.Bag(os.path.join(bag_dir,bag_file),"r")
        print(f"Saving poses and images from bag file {bag_number}/{len(bags)-1}.")
        bag_number+=1
        
        for (topic, msg, t) in bag.read_messages(topics=['/gnc/ekf',img_topic]):

            if topic == img_topic:
                cv_img = bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough")
                rgb = cv2.cvtColor(cv_img, cv2.COLOR_BayerGR2RGB) 
                image_time.append(t)
                cv2.imwrite(os.path.join(output_dir, f"{t}.jpg"), rgb)
            
            elif topic == '/gnc/ekf':
                pose = msg.pose
                trans = np.array([pose.position.x, pose.position.y, pose.position.z])
                quat_xyzw = [pose.orientation.x,pose.orientation.y,pose.orientation.z,pose.orientation.w]
                quat_wxyz = Quaternion(w=quat_xyzw[3],x=quat_xyzw[0],y=quat_xyzw[1],z=quat_xyzw[2])
                transf = quat_wxyz.transformation_matrix
                transf[0:3,3] = trans.T
                transform = np.linalg.inv(jpm_to_world)@transf@body_to_cam_transf
                pose_list.append(transform)
                pose_time.append(t)

        bag.close()

    for image_t in sorted(image_time):
        diff = []
        pose_time_pairs = zip(pose_time,pose_list)
        sorted_pairs = sorted(pose_time_pairs, key=lambda x: x[0])
        sorted_pose_time, sorted_pose_list = zip(*sorted_pairs)

        for pose_t in sorted_pose_time:
            diff.append(abs(pose_t-image_t))
        i = np.argmin(diff)
        saved_pose = sorted_pose_list[i]
        saved_t = sorted_pose_time[i]
        np.savetxt(f'{output_dir_poses}/{saved_t}.txt', saved_pose)

if __name__ == "__main__":
    main()