from __future__ import print_function
import cv2 as cv
import yaml
from datetime import datetime
import time
import os.path
from os import path
import shutil
from controller import Controller
from coordinates_generator import CoordinatesGenerator
from colors import *
from multiprocessing import Lock
from multiprocessing.pool import ThreadPool
from collections import deque
from carpark_data import CarParkData
from common import draw_str, draw_str_green, draw_str_red
import video
import cx_Oracle
import base64

def init_child(lock_):
    global lock
    lock = lock_
    
capture_duration = 1


def setPoints(frame):
    if path.exists('images/p1.png'):
        os.remove('images/p1.png')
    cv.imwrite('images/p1.png', frame)
    with open('data/coordinates_1.yml', "w+") as points:
        generator = CoordinatesGenerator('images/p1.png', points, COLOR_RED)
        generator.generate()
        
def getPoints(frame, points):
    if path.exists('data/coordinates_1.yml'):
        return points
    else:
        setPoints(frame)
        try:
            with open('data/coordinates_1.yml', "r") as data:
                try:
                    points = yaml.safe_load(data)
                except yaml.YAMLError as exc:
                    print(exc)
        except IOError:
            print ("Could not open file! Please close data/coordinates_1.yml !")
        return points

def captureShortIntervalVideos(cap, lock):
    with lock:
        startDateTime = datetime.now()
        destinationDirectoryStr = startDateTime.strftime('FROM_%d_%m_%Y_%H_%M_%S_TO')
        current_directory = os.getcwd() + '\\captured_videos'
        
        out = cv.VideoWriter(current_directory + '\\output.mp4', 0x00000021, 5, (640,480))
            
        start_time = time.time()
        while( int(time.time() - start_time) < capture_duration ):
            ret, frame = cap.read()
            if ret==True:
                out.write(frame)
            else:
                break
        
        out.release()
        
        endDateTime = datetime.now()
        destinationDirectoryStr = destinationDirectoryStr + endDateTime.strftime('_%d_%m_%Y_%H_%M_%S')
        print('Current Timestamp : ', destinationDirectoryStr)
            
        
        final_directory = os.path.join(current_directory, destinationDirectoryStr)
        if not os.path.exists(final_directory):
            os.makedirs(final_directory)
                
        shutil.move(current_directory + '\\output.mp4', final_directory + '\\output.mp4')
        return None, None

def persistSmartParkRealTime(carParkId, createDateTime, total_slots, available_slots, 
                             carpark_status, modifiedDateTime, carpark_image):
    
    sql = ('insert into smart_parking(carpark_id, created_date_time, total_slots, ' + 
           'available_slots, carpark_status, modified_date_time, carpark_image, precise_counter) ' +
           'values(:carpark_id, :created_date_time, :total_slots, :available_slots, ' +
           ':carpark_status, :modified_date_time, :carpark_image, :precise_counter)')
    try:
        # establish a new connection
        with cx_Oracle.connect('gsmuser/oracle@//localhost:1521/orcl') as connection:
            # create a cursor
            with connection.cursor() as cursor:
                # execute the insert statement
                cursor.execute(sql, [carParkId, createDateTime, total_slots, available_slots, carpark_status, 
                                     modifiedDateTime, carpark_image, time.time_ns()])
                # commit work
                connection.commit()
    except cx_Oracle.Error as error:
        print('SQL Error occurred:')
        print(error)

def isSmartParkingDBReady():
    sql = ('select is_smart_parking_ready from smart_parking_is_ready')
    try:
        # establish a new connection
        with cx_Oracle.connect('gsmuser/oracle@//localhost:1521/orcl') as connection:
            # create a cursor
            with connection.cursor() as cursor:
                result = cursor.execute(sql)       
                for row in result:
                    if str(row[0]) == 'Y':
                        return True
                    else:
                        return False
                
    except cx_Oracle.Error as error:
        print('SQL Error occurred:')
        print(error)

    

def main():
    import sys
    
    if path.exists('data/coordinates_1.yml'):
        os.remove('data/coordinates_1.yml')
        
    points = None
    carPark = None
    
    try:
        fn = sys.argv[1]
    except:
        fn = 1
    cap = video.create_capture(fn)


    def process_frame(ctrl, lock):
        with lock:
            frames, carPark = ctrl.runController()
            return frames, carPark

    threadn = cv.getNumberOfCPUs()
    pending = deque()
    lock = Lock()
    pool = ThreadPool(processes = threadn, initializer = init_child, initargs=(lock,))
    threaded_mode = True
    lastsave = 0
    
    pointsCaptured = False
    while True:
        
        while len(pending) > 0 and pending[0].ready() and pending[1].ready():
            frames, evaluated_carPark = pending.popleft().get()
            #latency.update(clock() - t0)
            if frames == None and evaluated_carPark == None:
                break
            else:
                for res in [*frames[0].values()]:
                   
                  
                    draw_str(res, (5, 20), CarParkData.TOTAL_NUMBER_OF_SLOTS
                             + str(evaluated_carPark.get_total_car_park_slots()))  
                    draw_str(res, (5, 40), CarParkData.NUMBER_OF_CARPARK_SLOTS_AVAILABLE 
                             + str(evaluated_carPark.get_available_carpark_slots()))
                    
                    if carPark.is_carpark_full():
                        draw_str_red(res, (5, 60), CarParkData.CARPARK_FULL_MESSAGE)
                    else:
                        draw_str_green(res, (5, 60), CarParkData.CARPARK_AVAILABLE_MESSAGE)
                    
                    #latest_modified_date_time = datetime.now()
                    #draw_str(res, (440,20), latest_modified_date_time.strftime('%d-%m-%Y %H:%M:%S '))
                    
                    if isSmartParkingDBReady():
                       # json = '['
                       # for carpark_slot in evaluated_carPark.get_carpark_slots():
                            #json = json + carpark_slot.toJSON() + ','
                        #json = json[:-1]
                        #json = json + ']'
                        #json = json.replace('\n','');
                        #json = json.replace('\t','');
                        #json = json.replace('\r','');
                        #retval, buffer = cv.imencode('.jpg', res)
                        #jpg_as_text = base64.b64encode(buffer)
                        
                        #persistSmartParkRealTime(evaluated_carPark.get_carpark_name(), 
                                                 #evaluated_carPark.get_carpark_creation_time(), 
                                                 #evaluated_carPark.get_total_car_park_slots(),
                                                 #evaluated_carPark.get_available_carpark_slots(),
                                                 #json, latest_modified_date_time, jpg_as_text)
                        if time.time() - lastsave > 1:
                            lastsave = time.time()
                            persistSmartParkRealTime(None, 
                                                 None, 
                                                 evaluated_carPark.get_total_car_park_slots(),
                                                 evaluated_carPark.get_available_carpark_slots(),
                                                 None, None, None)
                    
                    cv.namedWindow('smart-parking', cv.WINDOW_NORMAL)
                    cv.setWindowProperty('smart-parking', 0, 1)
                    
                    cv.imshow('smart-parking', res)
                    
                
        if len(pending) < threadn:
            
            if not pointsCaptured:
                _ret, frame = cap.read()
                points = getPoints(frame, points)
                carPark = CarParkData('SmartCarPark', len(points), datetime.now())
                ctrl = Controller(points, None, None, carPark)
                pointsCaptured = True
           
            if threaded_mode:
                task_on_videos = pool.apply_async(captureShortIntervalVideos, (cap, lock))
                task_on_frame_collection = pool.apply_async(process_frame, (ctrl, lock))
            
            pending.append(task_on_videos)
            pending.append(task_on_frame_collection)
        
        ch = cv.waitKey(1)
        if ch == ord(' '):
            threaded_mode = not threaded_mode
        if ch == 27:
            break

    print('Done')
    cap.release()


if __name__ == '__main__':
    print(__doc__)
    main()
    if path.exists('data/coordinates_1.yml'):
        os.remove('data/coordinates_1.yml')
    cv.destroyAllWindows()