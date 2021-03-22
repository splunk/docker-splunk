# Splunk Docker Images on Kubernetes

### Getting Started

* You will require access to a Kubernetes Cluster. Some options include:

```
Docker for Mac: https://docs.docker.com/docker-for-mac/
EKS walkthrough: https://www.splunk.com/blog/2018/07/19/splunk-connect-for-kubernetes-on-eks.html
Minikube: https://kubernetes.io/docs/tasks/tools/install-minikube/
Heptio AWS Quickstart: https://aws.amazon.com/quickstart/architecture/heptio-kubernetes/
Openshift AWS Quickstart: https://aws.amazon.com/quickstart/architecture/openshift/
```
WARNING!! Running complex Splunk deployments on your laptop will make it hot and slow!! These examples are suited for k8s clusters with appropriate specs, like the ones mentioned in the EKS and AWS quickstarts. To avoid melting your laptop, consider sticking to the ```3idx1sh1cm``` example, as it is usually more than enough for local development and small to medium Enterprise quickstarts. The larger deploy demonstrated here, explores a "lift and shift" of typical Enterprise deploys and assumes Enterprise grade specs. 


* Images

Pull the latest docker image into your environment using ```docker pull splunk/splunk:latest```

The example yamls are configured to pull from ```splunk/splunk:latest```. Ensure to update the image location if you are going to be pulling from a different repo. 

* Namespace

This deployment assumes you are deploying to a namespace called ```splunk```. If you would like to change the namespace, you can update the kubectl commands or update the yamls to include the namespace. You will also need to update the ```dnsConfig``` for the statefulsets accordingly:

``` 
dnsPolicy: ClusterFirst
      dnsConfig:
        searches:
          - indexer.splunk.svc.cluster.local
```

Where the search domain would consist of ```indexer.yourNamespace.svc.cluster.local``` 

See https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/#pod-identity for more info on statefulset identities/DNS. 

You will want to review your Kubernetes API Version and Spec to ensure DNS is configured to allow resolution of the names given to your pods. This is key especially in the SHC bootstrap process.

### NGINX

The new Splunk Docker image contains logic that allows your default.yml and license files to be centrally served via url. 

To demonstrate this capability, Nginx will be used to host our default.yml and our license.

Assuming you have pulled splunk:latest successfully, you can navigate to the ```nginx-data-www``` folder and use the following command to generate a sample default.yml

```docker run splunk/splunk:latest create-defaults > ./default.yml```

Once you have generated your default.yaml and inserted your license XML into the mySplunkLicense.lic file, it should look something like this: 

```
cd nginx-data-www/
ls -la
total 16
drwxr-xr-x  4 mmodestino  staff   128 Sep 26 23:50 .
drwxr-xr-x  5 mmodestino  staff   160 Sep 26 22:35 ..
-rw-r--r--  1 mmodestino  staff  1443 Sep 26 18:18 mySplunkLicense.lic
-rw-r--r--  1 mmodestino  staff   856 Sep 26 23:50 default.yml
```

Then, from the nginx directory create your configmaps:

```kubectl -n splunk create configmap nginx-data-www --from-file=nginx-data-www```

Then create one for the sample nginx conf file:

```kubectl -n splunk create configmap nginx-config --from-file=nginx-static.conf```

The deploy the nginx manfests:

```kubectl -n splunk apply -f manifests```

If deployed successfully, you will have an nginx pod running:

```
#kubectl -n splunk get pods
NAME                              READY     STATUS    RESTARTS   AGE
splunk-defaults-cff5cb574-kzf9x   1/1       Running   0          8s
```

You should also be able to reach the nginx page serving the license and the defaults file from your browser, with ```kubectl -n splunk port-forward```. 

For example:

```
kubectl -n splunk port-forward splunk-defaults-cff5cb574-kzf9x 9999:80
```

then point your browser at `localhost:9999` or `curl localhost:9999` and you should see your files being served. 

Now that we have our license and default configurations in place, lets use them in our pods!


### Persistence

If you would like to explore the concept of ```persistent volumes```, variants of the deployments detailed below have been added under ```3idx1sh1cm-pvc``` and ```3idxic3shc1cm1lm1dep-pvc```. These deployments mount 2 volumes per image, one for ```/opt/splunk/etc/``` and one for ```/opt/splunk/var```. Indexers mount 10GB and 100GB respectively, and non indexers mount 10GB and 50GB. 

To get started, ensure your cluster has a ```storageClass``` defined, and review the reclaim policy:

```
$ kubectl get storageclass
NAME            PROVISIONER             AGE
gp2 (default)   kubernetes.io/aws-ebs   1h

$ kubectl describe storageclass gp2
Name:            gp2
IsDefaultClass:  Yes
Annotations:     kubectl.kubernetes.io/last-applied-configuration={"apiVersion":"storage.k8s.io/v1beta1","kind":"StorageClass","metadata":{"annotations":{"storageclass.beta.kubernetes.io/is-default-class":"true"},"name":"gp2","namespace":""},"parameters":{"type":"gp2"},"provisioner":"kubernetes.io/aws-ebs"}
,storageclass.beta.kubernetes.io/is-default-class=true
Provisioner:           kubernetes.io/aws-ebs
Parameters:            type=gp2
AllowVolumeExpansion:  <unset>
MountOptions:          <none>
ReclaimPolicy:         Delete
VolumeBindingMode:     Immediate
Events:                <none>

```

NOTE: This example demonstrates dynamic provisioning of volumes and was developed against AWS Heptio Quickstart/EKS. You will be required to cleanup any volumes or ensure the reclaim policy is set accordingly.  You may need to manually provision volumes if you plan to deploy across AZs, or set your storage class to serve from a certain region. Please consult Kubernetes Documentation/Administrator to find the solution that works for you. https://kubernetes.io/docs/concepts/storage/persistent-volumes/ 
 
You can set these parameters in the volumeClaimTemplates for the Search Head and Indexer Statefulsets:

```
 volumeClaimTemplates:
  - metadata:
      name: splunk-idxcluster-data
    spec:
      accessModes: [ "ReadWriteOnce" ]
      resources:
        requests:
          storage: 100Gi
  - metadata: 
      name: splunk-idxcluster-config
    spec:
      accessModes: [ "ReadWriteOnce" ]
      resources:
        requests:
          storage: 10Gi
```

or in the separate *-pvc.yaml included for each of non statefulset, which defines the ```persistentVolumeClaims``. For example:

```

$ cat splunk-master-pvc.yaml
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: splunk-master-data
  namespace: splunk
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 50Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: splunk-master-config
  namespace: splunk
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
```

To view the ```claims``` and ```physical volumes```:

```
$ kubectl -n splunk get pvc
NAME                                 STATUS    VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   AGE
splunk-captain-config                Bound     pvc-6d914f67-e385-11e8-a6c2-028438484852   10Gi       RWO            gp2            10m
splunk-captain-data                  Bound     pvc-6d840332-e385-11e8-a6c2-028438484852   50Gi       RWO            gp2            10m
splunk-deployer-config               Bound     pvc-6ce21449-e385-11e8-a6c2-028438484852   10Gi       RWO            gp2            10m
splunk-deployer-data                 Bound     pvc-6cd6673f-e385-11e8-a6c2-028438484852   50Gi       RWO            gp2            10m
splunk-idxcluster-config-indexer-0   Bound     pvc-6cfc1b4e-e385-11e8-a6c2-028438484852   10Gi       RWO            gp2            10m
splunk-idxcluster-config-indexer-1   Bound     pvc-7cde53ff-e385-11e8-a6c2-028438484852   10Gi       RWO            gp2            10m
splunk-idxcluster-config-indexer-2   Bound     pvc-8fb4d5c3-e385-11e8-a6c2-028438484852   10Gi       RWO            gp2            9m
splunk-idxcluster-data-indexer-0     Bound     pvc-6cfb46d4-e385-11e8-a6c2-028438484852   100Gi      RWO            gp2            10m
splunk-idxcluster-data-indexer-1     Bound     pvc-7cdfab8c-e385-11e8-a6c2-028438484852   100Gi      RWO            gp2            10m
splunk-idxcluster-data-indexer-2     Bound     pvc-8fb42369-e385-11e8-a6c2-028438484852   100Gi      RWO            gp2            9m
splunk-license-config                Bound     pvc-6d2ba9aa-e385-11e8-a6c2-028438484852   10Gi       RWO            gp2            10m
splunk-license-data                  Bound     pvc-6d20697e-e385-11e8-a6c2-028438484852   50Gi       RWO            gp2            10m
splunk-master-config                 Bound     pvc-6d5eb358-e385-11e8-a6c2-028438484852   10Gi       RWO            gp2            10m
splunk-master-data                   Bound     pvc-6d549167-e385-11e8-a6c2-028438484852   50Gi       RWO            gp2            10m
splunk-search-config-search-0        Bound     pvc-6dba3eb0-e385-11e8-a6c2-028438484852   10Gi       RWO            gp2            10m
splunk-search-config-search-1        Bound     pvc-7b4bc7a5-e385-11e8-a6c2-028438484852   10Gi       RWO            gp2            10m
splunk-search-data-search-0          Bound     pvc-6db96eb7-e385-11e8-a6c2-028438484852   100Gi      RWO            gp2            10m
splunk-search-data-search-1          Bound     pvc-7b4aca3d-e385-11e8-a6c2-028438484852   100Gi      RWO            gp2            10m

$ kubectl -n splunk get pv
NAME                                       CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS    CLAIM                                       STORAGECLASS   REASON    AGE
pvc-6cd6673f-e385-11e8-a6c2-028438484852   50Gi       RWO            Delete           Bound     splunk/splunk-deployer-data                 gp2                      13m
pvc-6ce21449-e385-11e8-a6c2-028438484852   10Gi       RWO            Delete           Bound     splunk/splunk-deployer-config               gp2                      13m
pvc-6cfb46d4-e385-11e8-a6c2-028438484852   100Gi      RWO            Delete           Bound     splunk/splunk-idxcluster-data-indexer-0     gp2                      13m
pvc-6cfc1b4e-e385-11e8-a6c2-028438484852   10Gi       RWO            Delete           Bound     splunk/splunk-idxcluster-config-indexer-0   gp2                      13m
pvc-6d20697e-e385-11e8-a6c2-028438484852   50Gi       RWO            Delete           Bound     splunk/splunk-license-data                  gp2                      13m
pvc-6d2ba9aa-e385-11e8-a6c2-028438484852   10Gi       RWO            Delete           Bound     splunk/splunk-license-config                gp2                      13m
pvc-6d549167-e385-11e8-a6c2-028438484852   50Gi       RWO            Delete           Bound     splunk/splunk-master-data                   gp2                      13m
pvc-6d5eb358-e385-11e8-a6c2-028438484852   10Gi       RWO            Delete           Bound     splunk/splunk-master-config                 gp2                      13m
pvc-6d840332-e385-11e8-a6c2-028438484852   50Gi       RWO            Delete           Bound     splunk/splunk-captain-data                  gp2                      13m
pvc-6d914f67-e385-11e8-a6c2-028438484852   10Gi       RWO            Delete           Bound     splunk/splunk-captain-config                gp2                      13m
pvc-6db96eb7-e385-11e8-a6c2-028438484852   100Gi      RWO            Delete           Bound     splunk/splunk-search-data-search-0          gp2                      13m
pvc-6dba3eb0-e385-11e8-a6c2-028438484852   10Gi       RWO            Delete           Bound     splunk/splunk-search-config-search-0        gp2                      13m
pvc-7b4aca3d-e385-11e8-a6c2-028438484852   100Gi      RWO            Delete           Bound     splunk/splunk-search-data-search-1          gp2                      13m
pvc-7b4bc7a5-e385-11e8-a6c2-028438484852   10Gi       RWO            Delete           Bound     splunk/splunk-search-config-search-1        gp2                      13m
pvc-7cde53ff-e385-11e8-a6c2-028438484852   10Gi       RWO            Delete           Bound     splunk/splunk-idxcluster-config-indexer-1   gp2                      13m
pvc-7cdfab8c-e385-11e8-a6c2-028438484852   100Gi      RWO            Delete           Bound     splunk/splunk-idxcluster-data-indexer-1     gp2                      13m
pvc-8fb42369-e385-11e8-a6c2-028438484852   100Gi      RWO            Delete           Bound     splunk/splunk-idxcluster-data-indexer-2     gp2                      12m
pvc-8fb4d5c3-e385-11e8-a6c2-028438484852   10Gi       RWO            Delete           Bound     splunk/splunk-idxcluster-config-indexer-2   gp2                      12m

```

To clean up, ```kubectl -n splunk delete pvc --all```


### 3idx1sh1cm - Recommended for most users. 

Return to the ```../test_scenarios/kubernetes``` folder and run the manifests:

```kubectl -n splunk apply -f 3idx1sh1cm```

This folder deploys a Cluster Master, 3 clustered Indexers and a single Search Head. 

```
$ kubectl -n splunk get pods

NAME                      READY     STATUS    RESTARTS   AGE
indexer-0                 1/1       Running   0          2m
indexer-1                 1/1       Running   0          2m
indexer-2                 1/1       Running   0          2m
master-55c7bcf764-8z5cj   1/1       Running   0          2m
search-6cb9945dbf-kbcfz   1/1       Running   0          2m

```

Once deployed, you can scale the indexing tier by using the command, ```kubectl scale statefulsets <stateful-set-name> --replicas=<new-replicas>```

To scale the Search Heads, you can use the command, ```kubectl scale deployment <deployment-name> --replicas=3```. This will add 2 more standalone Search Heads to the cluster.

To delete the deployments, run ```kubectl delete -f 3idx3sh1cm```

You could also run ```kubectl -n splunk delete statefulset <statefulset-name>``` or ```kubectl -n splunk delete deployment <deployment-name>```

### 3idxic3shc1cm1lm1dep 

To deploy this architecture run ```kubectl -n splunk apply -f 3idxc3shc1cm1lm1dep``` from the kubernetes directory. 

This folder of manifests will deploy a License Master, a Cluster Master, 3 clustered Indexers, 3 clustered Search Heads and a deployer. 

The manifests currently use emptyDir mounts but can easly be switched to use persistent volume claims to allow a user to persist data and configs. (examples to be added later)

```
$ kubectl -n splunk get pods

NAME                              READY     STATUS    RESTARTS   AGE
captain-7dc78ccf7f-ghjk8          1/1       Running   0          24s
deployer-9f6d7cf8c-q8c7f          1/1       Running   0          27s
indexer-0                         1/1       Running   0          26s
indexer-1                         1/1       Running   0          20s
indexer-2                         1/1       Running   0          13s
license-master-564cf888b5-ssp8b   1/1       Running   0          26s
master-5dcdd7b965-httjq           1/1       Running   0          25s
search-0                          1/1       Running   0          24s
search-1                          1/1       Running   0          16s

```

Once deployed, you can scale the search tier or indexing tier by using the command, ```kubectl -n splunk scale statefulsets <stateful-set-name> --replicas=<new-replicas>```

While the Master is a deployment resource and has the ability to be scaled, there is only ever one Master in today's Splunk (active with Hot standnby is the DR pattern), so while you COULD scale the master replicas, it makes no sense to at this time.  


### Kubernetes Resources:

https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/

https://kubernetes.io/docs/concepts/workloads/controllers/deployment/

https://kubernetes.io/docs/concepts/services-networking/service/

https://kubernetes.io/docs/concepts/storage/persistent-volumes/


### Kubernetes Tips:

* Use ```kubectl -n splunk logs -f <podname>``` to watch for the Ansible plays to finish. 
* Once completed, you can then use ```kubectl -n splunk port-forward <podname> 9999:8000``` then visit ```localhost:9999``` in your browser to reach splunkweb on your instance.
* https://kubernetes.io/docs/reference/kubectl/cheatsheet/
* Clean up pvc with ```kubectl -n splunk delete pvc --all```


### Other useful commands:

export kubeconfig environment variable from current directory - ```export KUBECONFIG=$(pwd)/<your-kubeconfig>```

show pods in the splunk name space with wide output - ```kubectl -n splunk get pods -o wide```

show your deployments - ```kubectl -n splunk get deployments```

show your statefulsets - ``` kubectl -n splunk get statefulsets```

get service endpoints and external ip when using load balancers - ```kubectl -n splunk get svc -o wide```

describe your pod - ```kubectl -n splunk describe pod <podname>```

view the configmap the new containers require at startup - ```kubectl -n splunk describe configmap splunk-defaults```

