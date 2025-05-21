import re
import struct
from collections import deque

import serial

from client import *

# 写入优先级: 手动控制数据 > 路径控制数据 > 坐标数据
# 数据写入进程锁
write_thread_lock = threading.Lock()
# 手动控制进程锁
manual_thread_lock = threading.Lock()
# 路径执行结束标志
route_finish_flag = 1
# 小车坐标
deque location_data = deque(maxlen=1)
# 路径控制数据
route_data_list = deque(maxlen=100)
# 手动控制数据
manual_data_list = deque(maxlen=1)
# 卡尔曼参数
kalman_data_list = deque(maxlen=1)
kalman_data_list.extend([{'Q': (0.001 * np.eye(4)).tolist(), 'R': (0.0001 * np.eye(2)).tolist(), 'P': 0, 'I': 0, 'D': 0,
                          'really_angle': 0, 'Kalman_location_x': 0, 'Kalman_location_y': 0}])

# STM32数据
STM32_data = ""

# 控制模式切换时间
switch_time = 2
location_time = time.time() - switch_time
route_time = time.time() - switch_time
manual_time = time.time()


# 获取小车坐标数据并封包
def get_car_location_package(location_data_list):
    location_x = location_data_list[0]['x'] * 10
    location_y = location_data_list[0]['y'] * 10
    location_angle = 0
    location_data_package = struct.pack('10B', int('AA', 16), int('FD', 16), 10, (int(location_x) >> 8),
                                        (int(location_x) & 0xff), (int(location_y) >> 8), (int(location_y) & 0xff),
                                        (location_angle >> 16), (location_angle & 0xff), int('BB', 16))
    # print('location package: ', location_data_package.hex())
    return location_data_package


# 获取路径控制数据并封包
def get_car_route_package(route_data_list):
    global location_data_list
    route_x_1 = location_data_list[0]['x'] * 10
    route_y_1 = location_data_list[0]['y'] * 10
    route_x_2 = route_data_list[0]['x'] * 10
    route_y_2 = route_data_list[0]['y'] * 10
    route_data_package = struct.pack('13B', int('AA', 16), int('FE', 16), int('0D', 16), int('02', 16),
                                     (int(route_x_1) >> 8), (int(route_x_1) & 0xff), (int(route_y_1) >> 8),
                                     (int(route_y_1) & 0xff), (int(route_x_2) >> 8), (int(route_x_2) & 0xff),
                                     (int(route_y_2) >> 8), (int(route_y_2) & 0xff), int('BB', 16))
    print('route', route_x_1, route_y_1, route_x_2, route_y_2)
    # print('route package: ', route_data_package.hex())
    return route_data_package


# 获取手动控制数据并封包
def get_car_manual_package(manual_data_list):
    angle = manual_data_list[0]['angle']
    if angle > 0:
        turn_flag = 0x01
    else:
        turn_flag = 0x00
    angle = abs(angle)
    accelerator = manual_data_list[0]['accelerator'] / 10
    brake = manual_data_list[0]['brake'] / 10
    manual_data_package = struct.pack('8B', int('AA', 16), int('F0', 16), int('08', 16), turn_flag, int(angle),
                                      int(accelerator), int(brake), int('BB', 16))
    print('manual package: ', manual_data_package.hex())
    return manual_data_package


# 卡尔曼滤波
def kalman_filter(x, y):
    X2 = np.mat([[0], [0], [0], [0]])
    P2 = np.eye(4)
    F2 = np.mat([[1, 0, 1, 0], [0, 1, 0, 1], [0, 0, 1, 0], [0, 0, 0, 1]])
    Q2 = 0.001 * np.eye(4)
    H2 = np.mat([[1, 0, 0, 0], [0, 1, 0, 0]])
    R2 = 0.0001 * np.eye(2)
    lx = []
    ly = []
    lx.append(x)
    ly.append(y)
    z = np.mat([lx, ly])
    resultX = []
    resultY = []
    for i in range(len(lx)):
        _X2 = F2 * X2
        _P2 = F2 * P2 * F2.H + Q2
        K2 = _P2 * H2.H * (H2 * _P2 * H2.H + R2).I
        X2 = _X2 + K2 * (z[:, i] - H2 * _X2)
        P2 = (np.eye(4) - K2 * H2) * _P2
        resultX.append(X2[0].tolist())
        resultY.append(X2[1].tolist())
    predictX = np.ravel(resultX)
    predictY = np.ravel(resultY)
    predict_position = predictX.tolist() + predictY.tolist()
    # print('kalman filter result: ', predict_position)
    return predict_position


# 坐标通信回调
def location_message_callback(client, userdata, msg):
    global location_data_list

    message = eval(str(msg.payload, encoding="utf-8"))
    message_data = message['data']
    print('recv location package: ', message_data)
    location_data_list.extend(message_data)


# 控制通信回调
def control_message_callback(client, userdata, msg):
    global manual_thread_lock
    global route_data_list
    global manual_data_list
    global route_finish_flag
    global route_time
    global manual_time

    message = eval(str(msg.payload, encoding="utf-8"))
    message_data = message['data']
    if msg.topic == 'Route_mode':
        route_time = time.time()
        print('recv route message: ', message_data)
        route_data_list.clear()
        route_finish_flag = 1
        route_data_list.extend(message_data)
        # for route_data in message_data:
        #     route_data_list.append(route_data)
    elif msg.topic == 'Manual_mode':
        manual_time = time.time()
        if not manual_thread_lock.locked():
            print('switch to manual control mode')
            manual_thread_lock.acquire()
            route_data_list.clear()
            route_finish_flag = 1
        print('recv manual message: ', message_data)
        angle = message_data[0]['angle']
        if angle >= 0:
            angle = (angle / 32767) * 180 * 1.25
        else:
            angle = (angle / 32768) * 180 * 1.25
        accelerator = 80 * (1 - (message_data[0]['accelerator'] + 32768) / 65535)
        brake = 80 * (1 - (message_data[0]['brake'] + 32768) / 65535)
        manual_data = [{'angle': angle, 'accelerator': accelerator, 'brake': brake}]
        manual_data_list.extend(manual_data)


# 卡尔曼数据上传
def kalman_message_publish(topic=None, index=0):
    global publish_client_1
    global kalman_data_list

    if topic == None:
        topic = publish_client_1.topic[index]
    else:
        topic = topic[index]
    while True:
        message_data = kalman_data_list[0]
        message = json.dumps({'data': [message_data]})
        message = f'{message}'
        publish_client_1.client.publish(topic[0], message, qos=topic[1])
        # print('publish kalman package: ', message)
        time.sleep(0.5)


# Done数据上传
def Route_done_publish(topic=None, index=0):
    global publish_client_2

    if topic == None:
        topic = publish_client_2.topic[index]
    else:
        topic = topic[index]
    message_data = {'route_done': 1}
    message = json.dumps({'data': [message_data]})
    message = f'{message}'
    publish_client_1.client.publish(topic[0], message, qos=topic[1])
    print('publish route done: ', message)


# mqtt客户端启动
def MQTT_client_start():
    global subscribe_client_1, subscribe_client_2, publish_client_1, publish_client_2

    subscribe_client_1 = MQTT_Subscribe_Client(broker='192.168.0.142', port=1883, topic=[('Location', 0)],
                                               username='PythonReceive', password='**********')
    subscribe_client_2 = MQTT_Subscribe_Client(broker='192.168.0.142', port=1883,
                                               topic=[('Route_mode', 0), ('Manual_mode', 0)],
                                               username='PythonReceive', password='**********')
    publish_client_1 = MQTT_Publish_Client(broker='192.168.0.142', port=1883, topic=[('Raspberry_Kalman', 0)],
                                           username='PythonSend', password='**********')
    publish_client_2 = MQTT_Publish_Client(broker='192.168.0.142', port=1883, topic=[('Route_done', 0)],
                                           username='PythonSend', password='**********')

    subscribe_client_1.client.on_message = location_message_callback
    subscribe_client_2.client.on_message = control_message_callback

    subscribe_client_1.start()
    subscribe_client_2.start()
    publish_client_1.start()
    publish_client_2.start()

    subscribe_client_1.join()
    subscribe_client_2.join()
    publish_client_1.join()
    publish_client_2.join()


def str_to_json(input_string):
    # 创建空字典
    params_dict = {}

    # 切割字符串并生成键值对
    split_pairs = input_string.split(';')

    split_pairs = split_pairs[:-1]
    for pair in split_pairs:
        key, value = pair.split(':')
        params_dict[key] = float(value)

    return (params_dict)


# 读取串口回传数据
def read_callback_message(ser):
    global route_finish_flag
    global STM32_data
    global kalman_data_list

    # pattern = re.compile(r'angle:(-?\d+\.\d{3})\s(-?\d+\.\d{3})\s(-?\d+\.\d{3})', re.I)
    # pattern = re.compile(r'route done', re.I)
    pattern_1 = re.compile(r'\n', re.I)
    pattern_2 = re.compile(r';', re.I)
    while True:
        count = ser.inWaiting()
        if count > 0:
            data = ser.read(count).decode('utf-8')
            # print('callback message: ', data)
            STM32_data += data
            print("STM 32: ", STM32_data)
            data_list = re.split(pattern_1, STM32_data)
            if len(data_list) >= 2:
                for data in data_list:
                    result_list = re.split(pattern_2, data)
                    if "RD" in result_list:
                        route_finish_flag = 1
                        print("route done")
                        Route_done_publish()
                    if data[:2] == 'vx':
                        params = str_to_json(data)
                        if 'sita' in params:
                            kalman_data_list[0]['really_angle'] = params['sita']

                STM32_data = data_list[-1]
            if len(data_list) >= 3 and data_list[1][:2] == 'Kp':

                # 输入的字符串
                input_string = data_list[1]
                # 创建空字典
                # params_dict = {}
                # 切割字符串并生成键值对
                # split_pairs = input_string.split(';')
                if len(input_string) >= 36:
                    params_dict = str_to_json(input_string)
                    # split_pairs = split_pairs[:-1]
                    # for pair in split_pairs:
                    #    key, value = pair.split(':')
                    #    params_dict[key] = float(value)

                    # 将字典转换为JSON格式
                    # json_string = json.dumps(params_dict)

                    kalman_data_list[0]['P'] = params_dict['Kp']
                    kalman_data_list[0]['I'] = params_dict['Ki']
                    kalman_data_list[0]['D'] = params_dict['Kd']
        # time.sleep(0.1)


# 串口写入位置包
def write_actual_location_data(ser):
    global write_thread_lock
    global location_data_list

    while True:
        if not write_thread_lock.locked() and len(location_data_list) >= 1:
            # [location_data_list[0]['x'], location_data_list[0]['y']] = kalman_filter(location_data_list[0]['x'], location_data_list[0]['y'])
            package = get_car_location_package(location_data_list)
            # location_data_list.popleft()
            ser.write(package)
            # print('location package write success')
            time.sleep(0.05)


# 串口写入控制包
def write_control_data(ser):
    global write_thread_lock
    global manual_thread_lock
    global route_finish_flag
    global route_data_list
    global manual_data_list

    while True:
        if not manual_thread_lock.locked() and len(route_data_list) >= 1 and route_finish_flag:
            if len(route_data_list[0]) == 0:
                route_data_list.popleft()
                continue
            package = get_car_route_package(route_data_list)
            route_data_list.popleft()
            write_thread_lock.acquire()
            ser.write(package)
            print('route package write success', route_data_list)
            route_finish_flag = 0
            write_thread_lock.release()
            # time.sleep(0.1)
        elif manual_thread_lock.locked() and len(manual_data_list) >= 1:
            package = get_car_manual_package(manual_data_list)
            manual_data_list.popleft()
            write_thread_lock.acquire()
            ser.write(package)
            print('manual package write success', manual_data_list)
            write_thread_lock.release()
            # time.sleep(0.1)


# 控制模式转换
def control_mode_switch():
    global manual_thread_lock
    global switch_time
    global manual_time

    while True:
        if time.time() - manual_time >= switch_time and manual_thread_lock.locked():
            manual_thread_lock.release()
            route_data_list.clear()
            route_finish_flag = 1
            package = struct.pack('8B', int('AA', 16), int('F0', 16), int('08', 16), int('02', 16), int(0),
                                  int(0), int(0), int('BB', 16))
            ser.write(package)
            print('switch to route control mode')


if __name__ == '__main__':
    MQTT_client_start()

    ser = serial.Serial('/dev/ttyUSB1', 115200, timeout=0.5)

    read_port_thread = threading.Thread(target=read_callback_message, args=(ser,))
    read_port_thread.start()

    write_location_thread = threading.Thread(target=write_actual_location_data, args=(ser,))
    write_location_thread.start()

    write_control_thread = threading.Thread(target=write_control_data, args=(ser,))
    write_control_thread.start()

    control_mode_switch_thread = threading.Thread(target=control_mode_switch, args=())
    control_mode_switch_thread.start()

    kalman_message_publish()