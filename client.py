import json
import time
import random
import datetime
import threading
from socket import *
import paho.mqtt.client as mqtt_client


# 客户端父类, 用于完成客户端的回调绑定
class MQTTClient(threading.Thread):

    def __init__(self, broker='192.168.10.11', port=1883, topic=[('Kalman', 0)], username='PythonSend', password='**********'):
        super(MQTTClient, self).__init__()
        # 创建客户端
        client_id = f'python-mqtt-{random.randint(0, 1000)}'
        self.client = mqtt_client.Client(client_id=client_id)
        self.client.username_pw_set(username, password)
        # 配置代理端
        self.broker = broker
        self.port = port
        # 配置话题
        self.topic = topic
        # 配置行为回调
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_subscribe = self.on_subscribe
        self.client.on_unsubscribe = self.on_unsubscribe
        self.client.on_publish = self.on_publish
        self.client.on_message = self.on_message

    def run(self):
        self.thread = threading.currentThread()
        # 连接代理端
        self.client.connect(host=self.broker, port=self.port, keepalive=60)
        # 保持连接
        threading.Thread(target=self.client.loop_forever, args=()).start()

    # 创建连接回调
    # 输入: 客户端实例, 私有数据, 响应标识, 连接结果
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print('连接成功！', '地址', (self.broker, self.port), '主题', self.topic, '当前时间',
                  datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3])
        else:
            print('连接失败！', '地址', (self.broker, self.port), '主题', self.topic, '当前时间',
                  datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3])

    # 创建取消连接回调
    # 输入: 客户端实例, 私有数据, 断开结果
    def on_disconnect(self, client, userdata, rc):
        pass

    # 创建订阅回调
    # 输入: 客户端实例, 私有数据, 传出消息, 代理Qos表
    def on_subscribe(self, client, userdata, mid, granted_qos):
        pass

    # 创建取消订阅回调
    # 输入: 客户端实例, 私有数据, 传出消息, 代理Qos表
    def on_unsubscribe(self, client, userdata, mid, granted_qos):
        pass

    # 创建发布信息回调
    # 输入: 客户端实例, 私有数据, 传出消息
    def on_publish(self, client, userdata, mid):
        pass

    # 创建接受信息回调
    # 输入: 客户端实例, 私有数据, Message实例
    def on_message(self, client, userdata, msg):
        pass


# 订阅客户端子类
class MQTT_Subscribe_Client(MQTTClient):
    def __init__(self, broker='192.168.10.11', port=1883, topic=[('Kalman', 0)], username='PythonSend',
                 password='**********'):
        super(MQTT_Subscribe_Client, self).__init__(broker=broker, port=port, topic=topic,
                                                    username=username, password=password)

    def on_message(self, client, userdata, msg):
        super(MQTT_Subscribe_Client, self).on_message(client, userdata, msg)
        print('接收信息: ', msg.payload.decode(), '地址', (self.broker, self.port), '主题', msg.topic, '当前时间',
              datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3])

    def run(self):
        super(MQTT_Subscribe_Client, self).run()
        print('创建MQTT订阅客户端', '地址', (self.broker, self.port), '主题', self.topic, '当前时间',
              datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3], self.thread)
        self.client.subscribe(topic=self.topic)


# 发布客户端子类
class MQTT_Publish_Client(MQTTClient):
    def __init__(self, broker='192.168.10.11', port=1883, topic=[('Kalman', 0)], username='PythonSend',
                 password='**********'):
        super(MQTT_Publish_Client, self).__init__(broker=broker, port=port, topic=topic,
                                                  username=username, password=password)

    def run(self):
        super(MQTT_Publish_Client, self).run()
        print('创建MQTT发布客户端', '地址', (self.broker, self.port), '主题', self.topic, '当前时间',
              datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3], self.thread)

    def message_public(self, message, topic=None, index=0):
        if topic == None:
            topic = self.topic[index]
        else:
            topic = topic[index]
        message = f'{message}'
        result = self.client.publish(topic[0], message, qos=topic[1])
        status = result[0]
        if status == 0:
            print('发布成功！', '地址', (self.broker, self.port), '主题', topic, '当前时间',
                  datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3])
        else:
            print('发布失败！', '地址', (self.broker, self.port), '主题', topic, '当前时间',
                  datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3])


# UDP服务端父类
class UDP_Server(threading.Thread):
    def __init__(self, port=8888, buff_size=1024):
        super(UDP_Server, self).__init__()
        # 配置IP与端口
        self.host_name = gethostname()
        self.ip = gethostbyname(self.host_name)
        self.port = port
        # 配置缓存
        self.buff_size = buff_size
        # 创建套接字
        self.socket = socket(AF_INET, SOCK_DGRAM)
        # 绑定地址与端口
        self.address = (self.ip, port)

    def run(self):
        self.socket.bind(self.address)
        self.thread = threading.currentThread()
        print('创建UDP服务端', '地址', (self.host_name, self.address), '当前时间',
              datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3], self.thread)
        # 保持连接
        threading.Thread(target=self.message_wait_loop, args=()).start()

    def message_wait_loop(self):
        while True:
            print('等待数据......')
            # 接受UDP数据
            data, addr = self.socket.recvfrom(self.buff_size)
            print('接收到客户端数据: ', data, '地址', addr, '当前时间',
                  datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3])
            # 发送UDP数据
            content = '[%s] %s' % (bytes(time.ctime(), 'utf-8'), data.decode('utf-8'))
            self.socket.sendto(content.encode('utf-8'), addr)

    # 关闭连接
    def close(self):
        self.socket.close()


# UDP客户端父类
class UDP_Client(threading.Thread):
    def __init__(self, host_name=gethostname(), port=8888, buff_size=1024):
        super(UDP_Client, self).__init__()
        # 配置IP与端口
        self.host_name = host_name
        self.ip = gethostbyname(self.host_name)
        self.port = port
        # 配置缓存
        self.buff_size = buff_size
        # 创建套接字
        self.socket = socket(AF_INET, SOCK_DGRAM)
        # 绑定地址与端口
        self.address = (self.ip, port)

    def run(self):
        self.thread = threading.currentThread()
        print('创建UDP客户端', '地址', (self.host_name, self.address), '当前时间',
              datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3], self.thread)
        # 保持连接
        threading.Thread(target=self.message_send_loop, args=()).start()

    def message_send_loop(self):
        while True:
            data = input('>')
            if not data:
                break
            # 发送UDP数据
            self.socket.sendto(data.encode('utf-8'), self.address)
            # 接收UDP数据
            data, addr = self.socket.recvfrom(self.buff_size)
            if not data:
                break
            print('服务器端响应: ', data.decode('utf-8'), '地址', addr, '当前时间',
                  datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3])

    # 关闭连接
    def close(self):
        self.socket.close()


# UDP服务端-MQTT发布端子类
class UDP_MQTT_Server(UDP_Server):
    def __init__(self, udp_port=8888, buff_size=1024, broker='192.168.10.11', mqtt_port=1883, topic=[('Steering', 0)],
                 username='PythonSend', password='**********'):
        super(UDP_MQTT_Server, self).__init__(port=udp_port, buff_size=buff_size)
        self.mqtt_client = MQTT_Publish_Client(broker=broker, port=mqtt_port, topic=topic, username=username,
                                               password=password)

    def run(self):
        super(UDP_MQTT_Server, self).run()
        self.mqtt_client.start()

    def message_wait_loop(self):
        while True:
            print('等待数据......')
            # 接受UDP数据
            data, addr = self.socket.recvfrom(self.buff_size)
            if data:
                self.message_send(data)
                time.sleep(0.1)
            else:
                continue

    def message_send(self, data):
        data = data.decode('utf-8').split(',')
        message = {}
        message['angle'] = int(data[0])
        message['accelerator'] = int(data[1])
        message['brake'] = int(data[2])
        message = json.dumps([message])
        message = str({'data': message})
        print('发布信息: ', message, '地址', (self.host_name, self.address), '当前时间',
              datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3])
        self.mqtt_client.message_public(message)


if __name__ == '__main__':
    # # 实例化订阅客户端与发布客户端
    # subscribe_client = MQTT_Subscribe_Client()
    # publish_client = MQTT_Publish_Client()
    #
    # subscribe_client.start()
    # publish_client.start()
    #
    # subscribe_client.join()
    # publish_client.join()
    #
    # while True:
    #     message = {}
    #     # 卡尔曼滤波参数
    #     message['Q'] = np.random.random(size=(4, 4)).tolist()
    #     message['R'] = np.random.random(size=(2, 2)).tolist()
    #     # 相机软角度
    #     message['camera_angle'] = np.random.random(size=(3,)).tolist()
    #     # 角度计硬角度
    #     message['really_angle'] = np.random.random(size=(3,)).tolist()
    #     # 接收坐标
    #     message['receive_location'] = np.random.random(size=(3,)).tolist()
    #     # 卡尔曼滤波坐标
    #     message['kalman_location'] = np.random.random(size=(3,)).tolist()
    #     message = json.dumps([message])
    #     message = str({'data': message})
    #     publish_client.message_public(message)
    #     time.sleep(2)

    # 实例化转发服务端与订阅端
    udp_mqtt_server = UDP_MQTT_Server(broker='192.168.10.11', mqtt_port=1883, topic=[('Steering', 0)],
                                      username='PythonSend', password='**********')
    subscribe_client_1 = MQTT_Subscribe_Client(broker='192.168.10.11', port=1883,
                                               topic=[('hello', 0), ('Steering', 0), ('Route_mode', 0), ('Manual_mode', 0)],
                                               username='PythonRecv', password='**********')
    publish_client_1 = MQTT_Publish_Client(broker='192.168.10.11', port=1883, topic=[('hello', 0)], username='PythonSend',
                                           password='**********')
    publish_client_2 = MQTT_Publish_Client(broker='192.168.10.11', port=1883, topic=[('Route_mode', 0)], username='PythonSend',
                                           password='**********')
    publish_client_3 = MQTT_Publish_Client(broker='192.168.10.11', port=1883, topic=[('Manual_mode', 0)], username='PythonSend',
                                           password='**********')

    udp_mqtt_server.start()
    subscribe_client_1.start()
    publish_client_1.start()
    publish_client_2.start()
    publish_client_3.start()

    udp_mqtt_server.join()
    subscribe_client_1.join()
    publish_client_1.join()
    publish_client_2.join()
    publish_client_3.join()

    import numpy as np

    # 坐标数据
    location_data_list = [{'picid': 0, 'x': np.random.uniform(), 'y': np.random.uniform()}]
    message_1 = json.dumps({'data': location_data_list})
    # 路径数据
    route_data_list = []
    for each in range(np.random.randint(2, 10)):
        route_data_list.append({'datatype': 0, 'id': each, 'x': np.random.uniform(), 'y': np.random.uniform()})
    message_2 = json.dumps({'data': route_data_list})
    # 手动数据
    manual_data_list = [{'angle': 0, 'accelerator': 0, 'brake': 0}]
    message_3 = json.dumps({'data': manual_data_list})
    publish_client_1.message_public(message_1)
    time.sleep(1)
    publish_client_2.message_public(message_2)
    time.sleep(1)
    publish_client_3.message_public(message_3)
    time.sleep(1)
