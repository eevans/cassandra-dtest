import sys
sys.path = ['/home/tahooie/ccm', '/home/tahooie/automaton'] + sys.path

from dtest import Tester
from tools import *
from assertions import *
from ccmlib.cluster import Cluster
from ccmlib import common as ccmcommon
import random
import time
import threading

#from automaton.cluster.automation_modules import pycassa_util

import loadmaker

class ContinuousLoader(threading.Thread):
    """
    Hits the db continuously with LoadMaker. Can handle multiple kinds
    of loads (standard, super, counter, and super counter)

    Applies each type of load in a round-robin fashion

    """
    def __init__(self, node, load_makers=[]):
        """
        stress_arg_list is a list of stresses to run
        """
        self._node = node
        self._load_makers = load_makers
        self._inserting_lock = threading.Lock()
        self._is_loading = True
        super(ContinuousLoader, self).__init__()
        self.setDaemon(True)
        self.exception = None
        self.start()

    def run(self):
        """
        applies load whenever it isn't paused.
        """
        while True:
            for load_maker in self._load_makers:
                self._inserting_lock.acquire()
                try:
                    load_maker.generate(num_keys=100, server_list=[self._node.address()])
                except Exception, e:
                    # if anything goes wrong, store the exception
                    e.args = e.args + (str(load_maker), )
                    self.exception = (e, sys.exc_info()[2])
                    return
                finally:
                    self._inserting_lock.release()


    def check_exc(self):
        """
        checks to see if anything has gone wrong inserting data, and bails
        out if it has.
        """
        if self.exception:
            raise self.exception[0], None, self.exception[1]

    def read_and_validate(self, step=100):
        """
        reads back all the data that has been inserted.
        Pauses loading while validating. Cannot already be paused.
        """
        self.check_exc()
        self.pause()
        for load_maker in self._load_makers:
            load_maker.validate(step=step, server_list=[self._node.address()])
        self.unpause()

    def pause(self):
        """
        acquires the _inserting_lock to stop the loading from happening.
        """
        assert self._is_loading == True, "Called Pause while not loading!"
        self._inserting_lock.acquire()
        self._is_loading = False

    def unpause(self):
        """
        releases the _inserting_lock to resume loading.
        """
        assert self._is_loading == False, "Called Pause while loading!"
        self._inserting_lock.release()
        self._is_loading = True
        

class TestUpgrade(Tester):

    def __init__(self, *argv, **kwargs):
        super(TestUpgrade, self).__init__(*argv, **kwargs)
        self.allow_log_errors = True

    def rolling_upgrade_node(self, node, stress_node):
        """
        node is the node to upgrade. stress_ip is the node to run stress on.
        """
        print "Starting on upgrade procedure for node %s..." % node.name

        print "Creating LoadMaker.."
        lm_standard = loadmaker.LoadMaker(column_family_name='rolling_cf_standard',
                consistency_level='TWO')
        lm_super = loadmaker.LoadMaker(column_family_name='rolling_cf_super',
                column_family_type='super', num_cols=2, consistency_level='TWO')
        lm_counter_standard = loadmaker.LoadMaker(
                column_family_name='rolling_cf_counter_standard', 
                is_counter=True, consistency_level='TWO')
        loader = ContinuousLoader(stress_node, load_makers=
                [lm_standard, lm_super, lm_counter_standard])

        # let some load get in there
        print "sleeping"
        time.sleep(2)

        print "validating data..."
        loader.read_and_validate()
        print "done validating"
        


        # put some load on the cluster. 
#        args = [
#                    [   '--operation=INSERT', '--family-type=Standard', 
#                        '--num-keys=40000', '--consistency-level=TWO', 
#                        '--average-size-values', '--create-index=KEYS', 
#                        '--replication-factor=3', '--keep-trying=2',
#                        '--threads=1', '--nodes='+stress_node.address()],
#                    [   '--operation=INSERT', '--family-type=Super', 
#                        '--num-keys=20000', '--consistency-level=TWO', 
#                        '--average-size-values', '--create-index=KEYS', 
#                        '--replication-factor=3', '--keep-trying=2',
#                        '--threads=1', '--nodes='+stress_node.address()],
#                    [   '--operation=COUNTER_ADD', '--family-type=Standard', 
#                        '--num-keys=10000', '--consistency-level=ONE', 
#                        '--replication-factor=3', '--keep-trying=2',
#                        '--threads=1', '--nodes='+stress_node.address()],
#                    [   '--operation=COUNTER_ADD', '--family-type=Super', 
#                        '--num-keys=1', '--consistency-level=TWO', 
#                        '--replication-factor=3', '--keep-trying=2',
#                        '--threads=1', '--nodes='+stress_node.address()],
#                ]
#        print "Starting stress."
#        sm = StressMaker(stress_node, args)
#        print "sleeping 10 seconds..."
#        time.sleep(10) # make sure some data gets in before we shut down a node.
#        print "Done sleeping"
#    
#        print "Upgrading node: %s %s" % (node.name, node.address())
#        print "draining..."
#        node.nodetool('drain')
#        print "sleeping 1"
#        time.sleep(1)
#        print "stopping..."
#        node.stop(wait_other_notice=True)
#        print "sleeping 1"
#        time.sleep(1)
#        print "setting dir..."
#        try:
#            node.set_cassandra_dir(cassandra_version="cassandra")
#        except Exception, e:
#            new_exception = Exception("Did you clone and compile cassandra in $HOME/.ccm/repository/ ?"\
#                    " original exception: " + str(e))
#            raise new_exception
#        print "starting..."
#        node.start(wait_other_notice=True)
#        print "sleeping 1"
#        time.sleep(1)
#        print "scrubbing..."
#        node.nodetool('scrub')

#        if sm.is_alive():
#            print "The stress continued through the entire upgrade!"
#        else:
#            print "Need to send more keys to stress"

#        sm.join(120)


#        print "Reading back with stress"
#        args = [
#                    [   '--operation=READ', '--family-type=Standard', 
#                        '--num-keys=20000', '--consistency-level=ALL', 
#                        '--threads=10', '--keep-trying=2',
#                        '--nodes='+stress_node.address()],
#                    [   '--operation=READ', '--family-type=Super', 
#                        '--num-keys=20000', '--consistency-level=ALL', 
#                        '--threads=10', '--keep-trying=2',
#                        '--nodes='+stress_node.address()],
#                    [   '--operation=COUNTER_GET', '--family-type=Standard', 
#                        '--num-keys=10000', '--consistency-level=ALL', 
#                        '--threads=10', '--keep-trying=2',
#                        '--nodes='+stress_node.address()],
#                    [   '--operation=COUNTER_GET', '--family-type=Super', 
#                        '--num-keys=1', '--consistency-level=ALL', 
#                        '--threads=10', '--keep-trying=2',
#                        '--nodes='+stress_node.address()],
#        ]
#        sm = StressMaker(stress_node, args)
#        print "Waiting up to 60 seconds for the stress process to quit"
#        sm.join(60)

        print "Done upgrading node %s." % node.name


    def upgrade089_to_repo_test(self):
        cluster = self.cluster

        # Forcing cluster version on purpose
        cluster.set_cassandra_dir(cassandra_version="0.8.9")

        # Create a ring
        cluster.populate(3, tokens=[0, 2**125, 2**126]).start()
        [node1, node2, node3] = cluster.nodelist()
        cluster.start()

        time.sleep(.6)
        self.rolling_upgrade_node(node1, stress_node=node3)
#        self.rolling_upgrade_node(node2, stress_node=node3)
#        self.rolling_upgrade_node(node3, stress_node=node1)

        cluster.flush()

        cluster.cleanup()


    def static_upgrade_node(self, node, stress_node):
        """
        a less intense upgrade. Doesn't leave stress running while upgrading.
        Intended for upgrading from version .7.10
        """
        # put some load on the cluster. 
        args = [
                    [   '--operation=INSERT', '--family-type=Standard', 
                        '--num-keys=100', '--consistency-level=TWO', 
                        '--average-size-values', '--create-index=KEYS', 
                        '--replication-factor=3', '--keep-trying=2',
                        '--threads=1', '--nodes='+stress_node.address()],
                    [   '--operation=INSERT', '--family-type=Super', 
                        '--num-keys=100', '--consistency-level=TWO', 
                        '--average-size-values', '--create-index=KEYS', 
                        '--replication-factor=3', '--keep-trying=2',
                        '--threads=1', '--nodes='+stress_node.address()],
                ]
        sm = StressMaker(stress_node, args)
        sm.join(120)
    
        node.nodetool('drain')
        time.sleep(1)
        node.stop(wait_other_notice=True)
        time.sleep(1)
        try:
            node.set_cassandra_dir(cassandra_version="cassandra")
        except Exception, e:
            new_exception = Exception("Did you clone and compile cassandra in $HOME/.ccm/repository/ ?"\
                    " original exception: " + str(e))
            raise new_exception
        node.start(wait_other_notice=True)
        time.sleep(1)
        node.nodetool('scrub')

        args = [
                    [   '--operation=READ', '--family-type=Standard', 
                        '--num-keys=100', '--consistency-level=ALL', 
                        '--threads=10', '--keep-trying=2',
                        '--nodes='+stress_node.address()],
                    [   '--operation=READ', '--family-type=Super', 
                        '--num-keys=100', '--consistency-level=ALL', 
                        '--threads=10', '--keep-trying=2',
                        '--nodes='+stress_node.address()],
        ]
        sm = StressMaker(stress_node, args)
        sm.join(60)

#    def upgrade106_to_repo_test(self):
#        cluster = self.cluster

####         Forcing cluster version on purpose
#        cluster.set_cassandra_dir(cassandra_version="1.0.6")

####         Create a ring
#        cluster.populate(3, tokens=[0, 2**125, 2**126]).start()
#        [node1, node2, node3] = cluster.nodelist()

#        time.sleep(.5)
#        self.rolling_upgrade_node(node1, stress_node=node2)
#        self.rolling_upgrade_node(node2, stress_node=node3)
#        self.rolling_upgrade_node(node3, stress_node=node1)

#        cluster.flush()

#        cluster.cleanup()

#    def upgrade0710_to_repo_test(self):
#        cluster = self.cluster

####         Forcing cluster version on purpose
#        cluster.set_cassandra_dir(cassandra_version="0.7.10")

####         Create a ring
#        cluster.populate(3, tokens=[0, 2**125, 2**126]).start()
#        [node1, node2, node3] = cluster.nodelist()

#        time.sleep(.5)
#        self.rolling_upgrade_node(node1, stress_node=node2)
#        self.rolling_upgrade_node(node2, stress_node=node3)
#        self.rolling_upgrade_node(node3, stress_node=node1)

#        cluster.flush()

#        cluster.cleanup()
